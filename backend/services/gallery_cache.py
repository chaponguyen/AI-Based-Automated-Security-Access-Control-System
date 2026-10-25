# Agent 2 — Bộ nhớ cache kho embedding cư dân (B6 CP-02)
import logging
import threading
from typing import Dict, Optional, Tuple, Any
import numpy as np

logger = logging.getLogger(__name__)


class CachedUser:
    """Đối tượng lưu trữ thông tin cư dân trong RAM để truy xuất nhanh."""

    def __init__(
        self,
        id: int,
        full_name: str,
        age: int,
        apartment_number: str,
        status: str,
        user_code: Optional[str] = None,
    ):
        self.id = id
        self.full_name = full_name
        self.age = age
        self.apartment_number = apartment_number
        self.status = status
        self.user_code = user_code or f"USR{id:06d}"

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_code": self.user_code,
            "full_name": self.full_name,
            "age": self.age,
            "apartment_number": self.apartment_number,
            "status": self.status,
        }

    def __repr__(self) -> str:
        return f"<CachedUser id={self.id} name='{self.full_name}' status='{self.status}'>"


class _GallerySnapshot:
    """Bản chụp dữ liệu bất biến (immutable snapshot) đảm bảo an toàn luồng tuyệt đối."""

    def __init__(self, gallery: Dict[int, np.ndarray], users: Dict[int, CachedUser]):
        self.gallery = gallery  # {user_id: ndarray (n, 512)}
        self.users = users      # {user_id: CachedUser}
        self.total_users = len(users)
        self.total_vectors = sum(len(v) for v in gallery.values())
        self.active_users = sum(1 for u in users.values() if u.status == "active")
        self.inactive_users = sum(1 for u in users.values() if u.status == "inactive")


class GalleryCache:
    """Quản lý kho vector khuôn mặt trong bộ nhớ RAM phục vụ nhận diện.

    CP-02:
    - Nạp toàn bộ face_embeddings từ CSDL thành {user_id: ndarray (n, 512)}.
    - Lưu kèm thông tin người: tên, căn hộ, status (giữ cả cư dân inactive để nhận ra họ).
    - An toàn luồng: thay toàn bộ cấu trúc một lần bằng atomic pointer swap, không sửa tại chỗ.
    """

    def __init__(self):
        self._snapshot = _GallerySnapshot(gallery={}, users={})
        self._reload_lock = threading.Lock()

    def reload(self, db=None) -> Dict[str, int]:
        """Nạp lại toàn bộ dữ liệu từ CSDL vào cache.

        Có thể truyền db session có sẵn hoặc tự mở SessionLocal().
        """
        from database.models import User, FaceEmbedding

        session = db
        close_on_exit = False
        if session is None:
            from database.database import SessionLocal
            if SessionLocal is None:
                logger.warning("SessionLocal chưa sẵn sàng, không thể reload GalleryCache")
                return self.stats()
            session = SessionLocal()
            close_on_exit = True

        with self._reload_lock:
            try:
                # 1. Truy vấn toàn bộ cư dân (cả active và inactive)
                db_users = session.query(User).all()
                new_users: Dict[int, CachedUser] = {}
                for u in db_users:
                    new_users[u.id] = CachedUser(
                        id=u.id,
                        full_name=u.full_name,
                        age=u.age,
                        apartment_number=u.apartment_number,
                        status=u.status,
                        user_code=u.user_code,
                    )

                # 2. Truy vấn toàn bộ vector đặc trưng khuôn mặt
                db_embeddings = session.query(FaceEmbedding).all()
                emb_map: Dict[int, list] = {}
                for fe in db_embeddings:
                    if fe.embedding is not None and len(fe.embedding) == 512:
                        emb_map.setdefault(fe.user_id, []).append(fe.embedding)

                # 3. Gom thành ndarray (n, 512) float32 theo từng user
                new_gallery: Dict[int, np.ndarray] = {}
                for user_id, vectors in emb_map.items():
                    if user_id in new_users:
                        new_gallery[user_id] = np.array(vectors, dtype=np.float32)

                # 4. Atomic pointer swap: thay thế snapshot cũ bằng snapshot mới một lần
                new_snapshot = _GallerySnapshot(gallery=new_gallery, users=new_users)
                self._snapshot = new_snapshot

                stats = {
                    "users": new_snapshot.total_users,
                    "vectors": new_snapshot.total_vectors,
                    "active_users": new_snapshot.active_users,
                    "inactive_users": new_snapshot.inactive_users,
                }
                logger.info(
                    "GalleryCache đã nạp lại: %d cư dân (%d active, %d inactive), %d vector khuôn mặt",
                    stats["users"],
                    stats["active_users"],
                    stats["inactive_users"],
                    stats["vectors"],
                )
                return stats
            except Exception as e:
                logger.error("Lỗi khi reload GalleryCache: %s", e)
                raise e
            finally:
                if close_on_exit:
                    session.close()

    def get_gallery(self) -> Dict[int, np.ndarray]:
        """Trả về snapshot dict {user_id: ndarray (n, 512)} cho best_match."""
        return self._snapshot.gallery

    def get_user(self, user_id: int) -> Optional[CachedUser]:
        """Lấy thông tin cư dân từ cache theo user_id."""
        return self._snapshot.users.get(user_id)

    def get_users(self) -> Dict[int, CachedUser]:
        """Lấy toàn bộ từ điển cư dân từ cache."""
        return self._snapshot.users

    def update_resident_status(self, user_id: int, status: str) -> None:
        """Cập nhật trạng thái cư dân trong cache (atomic swap user info)."""
        current = self._snapshot
        user = current.users.get(user_id)
        if user is None:
            return

        # Tạo dict users mới với user đã cập nhật status
        updated_users = dict(current.users)
        updated_users[user_id] = CachedUser(
            id=user.id,
            full_name=user.full_name,
            age=user.age,
            apartment_number=user.apartment_number,
            status=status,
            user_code=user.user_code,
        )

        new_snapshot = _GallerySnapshot(gallery=current.gallery, users=updated_users)
        with self._reload_lock:
            self._snapshot = new_snapshot
        logger.info("GalleryCache đã cập nhật status của User %d -> %s", user_id, status)

    def stats(self) -> Dict[str, int]:
        """Thống kê số lượng người và số vector trong cache."""
        s = self._snapshot
        return {
            "users": s.total_users,
            "vectors": s.total_vectors,
            "active_users": s.active_users,
            "inactive_users": s.inactive_users,
        }


# Singleton toàn cục
_gallery_cache = GalleryCache()


def get_gallery_cache() -> GalleryCache:
    return _gallery_cache


def init_cache(db=None) -> Dict[str, int]:
    return _gallery_cache.reload(db)


def reload(db=None) -> Dict[str, int]:
    return _gallery_cache.reload(db)


def get_gallery() -> Dict[int, np.ndarray]:
    return _gallery_cache.get_gallery()


def get_user(user_id: int) -> Optional[CachedUser]:
    return _gallery_cache.get_user(user_id)


def update_resident_status(user_id: int, status: str) -> None:
    _gallery_cache.update_resident_status(user_id, status)


def stats() -> Dict[str, int]:
    return _gallery_cache.stats()
