"""Quản lý cờ điều khiển AI (tạm dừng khi đang quay video đăng ký cư dân).

CP-03 (B11): Tạo cờ paused = threading.Event() để B5 dùng được trước khi B12 xong.
B12 đọc cờ này mỗi vòng lặp, nếu đang paused thì bỏ qua không xử lý.
"""
import threading

# Cờ tạm dừng nhận diện AI
paused = threading.Event()


def pause_ai() -> None:
    """Tạm dừng vòng lặp nhận diện AI (dùng khi bắt đầu quay đăng ký cư dân)."""
    paused.set()


def resume_ai() -> None:
    """Tiếp tục vòng lặp nhận diện AI (dùng khi quay đăng ký xong)."""
    paused.clear()


def is_ai_paused() -> bool:
    """Kiểm tra AI có đang tạm dừng hay không."""
    return paused.is_set()
