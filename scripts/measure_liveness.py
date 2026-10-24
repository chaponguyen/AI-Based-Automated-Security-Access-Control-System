"""Đo APCER/BPCER cho B4 CP-05 (chống giả mạo, MiniFASNetV2).

Chạy:
    python scripts/measure_liveness.py
    python scripts/measure_liveness.py --real-dir test_data/real_webcam --spoof-dir test_data/spoof

Ghi docs/reports/B4_liveness.csv (điểm từng ảnh) và in bảng APCER/BPCER theo ngưỡng 0,40..0,80.
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

from ai.anti_spoof import liveness_score  # noqa: E402
from ai.detector import detect_faces  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
THRESHOLDS = [round(0.40 + 0.05 * i, 2) for i in range(9)]   # 0,40 .. 0,80


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


def main():
    parser = argparse.ArgumentParser(description="Do APCER/BPCER cho chong gia mao (B4 CP-05)")
    parser.add_argument("--real-dir", default=os.path.join(ROOT, "test_data", "real_webcam"))
    parser.add_argument("--spoof-dir", default=os.path.join(ROOT, "test_data", "spoof"))
    parser.add_argument("--extra-real-dir", default=os.path.join(ROOT, "test_data"),
                        help="nhom that tham khao them (mac dinh 10 selfie), de trong de bo qua")
    parser.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "B4_liveness.csv"))
    args = parser.parse_args()

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
