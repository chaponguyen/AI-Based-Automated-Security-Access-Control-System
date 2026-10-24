"""Đo APCER/BPCER cho B4 (chống giả mạo, MiniFASNetV2).

Chạy:
    python scripts/measure_liveness.py
    python scripts/measure_liveness.py --real-dir test_data/real_webcam --spoof-dir test_data/spoof
    python scripts/measure_liveness.py --clips

Ghi docs/reports/B4_liveness.csv (điểm từng ảnh) và in bảng APCER/BPCER theo ngưỡng 0,40..0,80.
Chế độ --clips: quét video ngắn trong test_data/ (live_video, spoof_photo, spoof_video),
theo dõi một mặt qua các khung rồi gọi check_liveness_sequence; ghi docs/reports/B4_clips.csv.
"""
import argparse
import csv
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from ai.anti_spoof import check_liveness_sequence, liveness_score  # noqa: E402
from ai.config import LIVENESS_SEQ_MAX_FRAMES  # noqa: E402
from ai.detector import detect_faces  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VEXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
THRESHOLDS = [round(0.40 + 0.05 * i, 2) for i in range(9)]   # 0,40 .. 0,80
CLIP_FPS = 10          # lấy mẫu ~10 khung/giây, đủ cho chuyển động mà không nặng máy
CLIP_FOLDERS = ("live_video", "spoof_photo", "spoof_video")


def list_images(folder):
    return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                  if os.path.splitext(n)[1].lower() in EXTS)


def measure(folder, label):
    rows = []
    for path in list_images(folder):
        image = cv2.imread(path)
        if image is None:
            rows.append({"nhom": label, "anh": os.path.basename(path), "so_mat": 0,
                         "trang_thai": "unreadable", "score": None, "ms": None})
            continue
        faces = detect_faces(image)
        if not faces:
            rows.append({"nhom": label, "anh": os.path.basename(path), "so_mat": 0,
                         "trang_thai": "no_face", "score": None, "ms": None})
            continue
        scores = []
        elapsed = 0.0
        for face in faces:
            t0 = time.perf_counter()
            scores.append(liveness_score(image, face["bbox"]))
            elapsed += time.perf_counter() - t0
        rows.append({"nhom": label, "anh": os.path.basename(path),
                     "so_mat": len(faces),
                     "trang_thai": "ok" if len(faces) == 1 else f"{len(faces)}_faces",
                     "score": max(scores), "ms": 1000.0 * elapsed / len(faces)})
    return rows


def rates(rows, threshold):
    spoof = [r for r in rows if r["nhom"] == "gia"]
    real = [r for r in rows if r["nhom"] == "that"]
    # Không phát hiện được mặt cũng coi là đã chặn ở bước trước.
    spoof_accepted = sum(1 for r in spoof
                         if r["score"] is not None and r["score"] >= threshold)
    real_rejected = sum(1 for r in real
                        if r["score"] is None or r["score"] < threshold)
    apcer = spoof_accepted / len(spoof) if spoof else float("nan")
    bpcer = real_rejected / len(real) if real else float("nan")
    return apcer, bpcer, spoof_accepted, len(spoof), real_rejected, len(real)


def _iou(a, b):
    ax1, ay1, ax2, ay2 = (float(v) for v in a)
    bx1, by1, bx2, by2 = (float(v) for v in b)
    ix = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    iy = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = ix * iy
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


def track_clip(path, fps_target=CLIP_FPS):
    """Đọc clip, lấy mẫu ~fps_target khung/giây, theo dõi MỘT mặt bằng IoU.

    Trả (frames, boxes, fps_goc, so_khung_doc). Khung không thấy mặt thì bỏ,
    khung sau nối với bbox gần nhất trước đó.
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"khong mo duoc clip: {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    step = max(1, int(round(src_fps / fps_target))) if src_fps > 0 else 1

    frames, boxes, last_box, read = [], [], None, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if read % step:
            read += 1
            continue
        read += 1
        faces = detect_faces(frame)
        if not faces:
            continue
        if last_box is None:
            face = max(faces, key=lambda f: (f["bbox"][2] - f["bbox"][0]) *
                       (f["bbox"][3] - f["bbox"][1]))
        else:
            face = max(faces, key=lambda f: _iou(last_box, f["bbox"]))
            if _iou(last_box, face["bbox"]) < 0.3:
                continue
        last_box = face["bbox"]
        frames.append(frame)
        boxes.append(last_box)
        if len(frames) > 2 * LIVENESS_SEQ_MAX_FRAMES:   # chỉ giữ lịch sử gần nhất
            frames.pop(0)
            boxes.pop(0)
    cap.release()
    return frames, boxes, src_fps, read


def measure_clips(folders):
    """Chạy check_liveness_sequence trên từng clip trong các thư mục."""
    rows = []
    for folder in folders:
        if not os.path.isdir(folder):
            print(f"  (bo qua, khong thay thu muc) {folder}")
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in VEXTS:
                continue
            nhom = os.path.basename(folder)
            try:
                frames, boxes, src_fps, read = track_clip(path)
            except IOError as exc:
                print(f"  LOI {name}: {exc}")
                continue
            if not frames:
                rows.append({"nhom": nhom, "clip": name, "fps": src_fps, "frames": 0,
                             "score": None, "motion": None, "std": None,
                             "is_real": False, "mode": "no_face"})
                continue
            is_real, score, detail = check_liveness_sequence(frames, boxes)
            rows.append({"nhom": nhom, "clip": name, "fps": src_fps,
                         "frames": detail.get("frames", len(frames)),
                         "score": score, "motion": detail.get("motion"),
                         "std": detail.get("std"), "is_real": is_real,
                         "mode": detail.get("mode", "?")})
    return rows


def print_clips(rows):
    print("\nKiem tra song theo thoi gian tren clip:")
    print("| Nhom | Clip | fps | So khung | Diem (trung vi) | Chuyen dong | Do lech | Ket luan |")
    print("|---|---|---:|---:|---:|---:|---:|---|")
    for r in rows:
        score = "-" if r["score"] is None else f"{r['score']:.4f}"
        motion = "-" if r["motion"] is None else f"{r['motion']:.3f}"
        std = "-" if r["std"] is None else f"{r['std']:.5f}"
        ket = "that" if r["is_real"] else "chan"
        print(f"| {r['nhom']} | {r['clip']} | {r['fps']:.0f} | {r['frames']} | "
              f"{score} | {motion} | {std} | {ket} ({r['mode']}) |")


def main():
    parser = argparse.ArgumentParser(description="Do APCER/BPCER cho chong gia mao (B4)")
    parser.add_argument("--real-dir", default=os.path.join(ROOT, "test_data", "real_webcam"))
    parser.add_argument("--spoof-dir", default=os.path.join(ROOT, "test_data", "spoof"))
    parser.add_argument("--extra-real-dir", default=os.path.join(ROOT, "test_data"),
                        help="nhom that tham khao them (mac dinh 10 selfie), de trong de bo qua")
    parser.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "B4_liveness.csv"))
    parser.add_argument("--clips", action="store_true",
                        help="che do clip: do liveness theo thoi gian tren video ngan")
    parser.add_argument("--clip-root", default=os.path.join(ROOT, "test_data"),
                        help="thu muc goc chua live_video/, spoof_photo/, spoof_video/")
    args = parser.parse_args()

    if args.clips:
        root = args.clip_root if os.path.isabs(args.clip_root) else os.path.join(ROOT, args.clip_root)
        folders = [os.path.join(root, name) for name in CLIP_FOLDERS]
        rows = measure_clips(folders)
        if not rows:
            print("Khong co clip nao. Dat clip vao:",
                  ", ".join(os.path.join(root, n) for n in CLIP_FOLDERS))
            return
        out_path = os.path.join(ROOT, "docs", "reports", "B4_clips.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["nhom", "clip", "fps", "so_khung", "score", "chuyen_dong",
                             "do_lech", "is_real", "mode"])
            for r in rows:
                writer.writerow([r["nhom"], r["clip"], f"{r['fps']:.0f}", r["frames"],
                                 "" if r["score"] is None else f"{r['score']:.6f}",
                                 "" if r["motion"] is None else f"{r['motion']:.4f}",
                                 "" if r["std"] is None else f"{r['std']:.6f}",
                                 int(bool(r["is_real"])), r["mode"]])
        print("Da ghi:", out_path)
        print_clips(rows)
        return

    real_dir = args.real_dir if os.path.isabs(args.real_dir) else os.path.join(ROOT, args.real_dir)
    spoof_dir = args.spoof_dir if os.path.isabs(args.spoof_dir) else os.path.join(ROOT, args.spoof_dir)
    out_path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    for folder in (real_dir, spoof_dir):
        if not os.path.isdir(folder):
            sys.exit(f"Khong thay thu muc: {folder}")

    rows = measure(spoof_dir, "gia") + measure(real_dir, "that")
    extra = []
    if args.extra_real_dir:
        extra_dir = (args.extra_real_dir if os.path.isabs(args.extra_real_dir)
                     else os.path.join(ROOT, args.extra_real_dir))
        if os.path.isdir(extra_dir):
            extra = measure(extra_dir, "that_selfie")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["nhom", "anh", "so_mat", "trang_thai", "score", "ms"])
        for r in rows + extra:
            writer.writerow([r["nhom"], r["anh"], r["so_mat"], r["trang_thai"],
                             "" if r["score"] is None else f"{r['score']:.6f}",
                             "" if r["ms"] is None else f"{r['ms']:.1f}"])
    print("Da ghi:", out_path)

    for label, group in (("GIA (spoof)", [r for r in rows if r["nhom"] == "gia"]),
                         ("THAT (real_webcam)", [r for r in rows if r["nhom"] == "that"]),
                         ("THAT (selfie, tham khao)", extra)):
        scored = [r["score"] for r in group if r["score"] is not None]
        no_face = sum(1 for r in group if r["trang_thai"] == "no_face")
        multi = sum(1 for r in group if r["so_mat"] > 1)
        print(f"\n{label}: {len(group)} anh | khong mat: {no_face} | nhieu mat: {multi}")
        if scored:
            times = [r["ms"] for r in group if r["ms"] is not None]
            print("  score min/trung binh/max: %.4f / %.4f / %.4f | TB %.1f ms/anh"
                  % (min(scored), float(np.mean(scored)), max(scored), float(np.mean(times))))
        for r in group:
            print("   %-28s mat=%d %-9s %s" % (
                r["anh"], r["so_mat"], r["trang_thai"],
                "-" if r["score"] is None else f"{r['score']:.4f}"))

    print("\nBang APCER/BPCER (APCER = ty le anh gia bi chap nhan, BPCER = ty le anh that bi chan nham):")
    print("| Nguong | APCER | BPCER | Anh gia lot | Anh that bi chan |")
    print("|---:|---:|---:|---:|---:|")
    for t in THRESHOLDS:
        apcer, bpcer, sa, sn, rr, rn = rates(rows, t)
        print(f"| {t:.2f} | {100*apcer:.1f}% ({sa}/{sn}) | {100*bpcer:.1f}% ({rr}/{rn}) | "
              f"{sn - sa} | {rr} |")

    if extra:
        print("\nBPCER tren nhom selfie (tham khao):")
        for t in THRESHOLDS:
            rejected = sum(1 for r in extra if r["score"] is None or r["score"] < t)
            print(f"  nguong {t:.2f}: {rejected}/{len(extra)} bi chan")


if __name__ == "__main__":
    main()
