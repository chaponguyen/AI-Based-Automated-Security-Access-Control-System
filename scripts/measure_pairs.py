"""Đo độ giống các cặp cùng người / khác người cho B3 CP-04.

Bố cục ưu tiên: test_data/people/<tên>/*.jpg
Nếu chưa có people/, coi cả thư mục dữ liệu là MỘT người (chỉ đo được cặp cùng người).

Chạy:
    python scripts/measure_pairs.py
    python scripts/measure_pairs.py --data-dir out/b3_demo --out docs/reports/B3_pairs.csv
"""
import argparse
import csv
import itertools
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import cv2  # noqa: E402

from ai.aligner import crop_face  # noqa: E402
from ai.detector import detect_faces  # noqa: E402
from ai.embedder import get_embedding  # noqa: E402
from ai.matcher import cosine  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def list_images(folder):
    paths = []
    for base, _dirs, files in os.walk(folder):
        for name in files:
            if os.path.splitext(name)[1].lower() in EXTS:
                paths.append(os.path.join(base, name))
    return sorted(paths)


def collect_people(data_dir):
    people_dir = os.path.join(data_dir, "people")
    if os.path.isdir(people_dir):
        people = []
        for name in sorted(os.listdir(people_dir)):
            path = os.path.join(people_dir, name)
            if os.path.isdir(path):
                people.append((name, path))
        return people, True
    # Chưa có people/: coi cả thư mục là một người để vẫn đo được cặp cùng người.
    return [(os.path.basename(os.path.abspath(data_dir)), data_dir)], False


def embed_folder(people):
    rows = []
    skipped = []
    for person, folder in people:
        for path in list_images(folder):
            rel = os.path.relpath(path, folder)
            image = cv2.imread(path)
            if image is None:
                skipped.append((person, rel, "unreadable"))
                continue
            faces = detect_faces(image)
            if len(faces) != 1:
                skipped.append((person, rel, f"{len(faces)}_faces"))
                continue
            emb = get_embedding(crop_face(image, faces[0]["kps"]))
            if emb is None:
                skipped.append((person, rel, "zero_embedding"))
                continue
            rows.append((person, rel, emb))
    return rows, skipped


def stats(values):
    if not values:
        return None
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
    }


def main():
    parser = argparse.ArgumentParser(description="Do cap do giong cung nguoi / khac nguoi (B3 CP-04)")
    parser.add_argument("--data-dir", default=os.path.join(ROOT, "test_data"))
    parser.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "B3_pairs.csv"))
    args = parser.parse_args()

    data_dir = args.data_dir if os.path.isabs(args.data_dir) else os.path.join(ROOT, args.data_dir)
    out_path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    if not os.path.isdir(data_dir):
        sys.exit(f"Khong thay thu muc du lieu: {data_dir}")

    people, has_people_dir = collect_people(data_dir)
    print(f"Du lieu: {data_dir}")
    print(f"Cau truc: {'people/<ten>/' if has_people_dir else 'phang - coi ca thu muc la 1 nguoi'}")
    print("So nguoi:", len(people), "| so thu muc co anh:", sum(1 for _, f in people if list_images(f)))

    rows, skipped = embed_folder(people)
    print(f"Anh dung duoc: {len(rows)} | bo qua: {len(skipped)}")
    for person, rel, why in skipped:
        print(f"  bo qua {person}/{rel}: {why}")
    if not rows:
        sys.exit("Khong co embedding nao, dung.")

    same, diff = [], []
    for (p1, i1, e1), (p2, i2, e2) in itertools.combinations(rows, 2):
        sim = cosine(e1, e2)
        if p1 == p2:
            same.append((p1, i1, i2, sim))
        else:
            diff.append((p1, i1, p2, i2, sim))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["nhom", "nguoi_a", "anh_a", "nguoi_b", "anh_b", "similarity"])
        for p1, i1, i2, sim in same:
            writer.writerow(["cung_nguoi", p1, i1, p1, i2, f"{sim:.6f}"])
        for p1, i1, p2, i2, sim in diff:
            writer.writerow(["khac_nguoi", p1, i1, p2, i2, f"{sim:.6f}"])
    print("Da ghi:", out_path)

    print()
    print(f"{'nhom':12s} {'so_cap':>7s} {'trung_binh':>10s} {'nho_nhat':>9s} {'lon_nhat':>9s}")
    print("-" * 52)
    s_same = stats([r[3] for r in same])
    s_diff = stats([r[4] for r in diff])
    for label, s in (("cung_nguoi", s_same), ("khac_nguoi", s_diff)):
        if s is None:
            print(f"{label:12s} {'0':>7s} {'-':>10s} {'-':>9s} {'-':>9s}")
        else:
            print(f"{label:12s} {s['count']:>7d} {s['mean']:>10.4f} {s['min']:>9.4f} {s['max']:>9.4f}")

    if not has_people_dir:
        print()
        print("CANH BAO: chua co test_data/people/<ten>/ nen chi do duoc cap cung nguoi.")
    if s_same and s_diff and s_same["min"] > s_diff["max"]:
        print(f"Goi y nguong o giua: {(s_same['min'] + s_diff['max']) / 2:.4f} "
              f"(min cung nguoi {s_same['min']:.4f}, max khac nguoi {s_diff['max']:.4f})")
    else:
        print("Chua tach duoc hai nhom bang mot nguong (thieu du lieu khac nguoi hoac hai nhom chong nhau).")


if __name__ == "__main__":
    main()
