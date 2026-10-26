"""Đo độ giống các cặp cùng người / khác người cho B3, và hiệu chỉnh SIM_THRESHOLD.

Bố cục dữ liệu (mặc định test_data/):
- Ảnh phẳng ở gốc (vd `1792...jpg`)      : selfie điện thoại của chủ dự án, nguồn "selfie".
- `real_webcam/*.jpg`                     : ảnh webcam của chủ dự án, nguồn "webcam".
- `other_people/<tên>/*.jpg`              : mỗi thư mục con là MỘT người lạ, nguồn "stranger".
- (tương thích cũ) `people/<tên>/*.jpg`   : mỗi thư mục con là một người.

Hai nguồn selfie và webcam được tách riêng vì cùng một người nhưng khác camera,
khác ánh sáng, khác tư thế — độ giống giữa hai nguồn thấp hơn trong cùng nguồn.

Chạy:
    python scripts/measure_pairs.py
    python scripts/measure_pairs.py --data-dir test_data --out docs/reports/B3_pairs.csv
"""
import argparse
import csv
import itertools
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

import ai.matcher as matcher_mod  # noqa: E402  (đổi ngưỡng tạm thời khi quét)
from ai.aligner import crop_face  # noqa: E402
from ai.detector import detect_faces  # noqa: E402
from ai.embedder import get_embedding  # noqa: E402
from ai.matcher import best_match, cosine  # noqa: E402

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SELF = "chu_du_an"          # khóa danh tính của chủ dự án
SRC_WEBCAM = "webcam"
SRC_SELFIE = "selfie"
SRC_STRANGER = "stranger"
SRC_PEOPLE = "people"

GROUP_LABELS = {
    "cung_webcam_webcam": "(a) cung nguoi: webcam x webcam",
    "cung_webcam_selfie": "(b) cung nguoi: webcam x selfie",
    "cung_selfie_selfie": "(c) cung nguoi: selfie x selfie",
    "khac_self_nguoila": "(d1) khac nguoi: chu du an x nguoi la",
    "khac_nguoila_nguoila": "(d2) khac nguoi: nguoi la x nguoi la",
    "cung_khac_nguon": "(x) cung nguoi, nguon khac (people/)",
}


def list_images(folder):
    paths = []
    for base, _dirs, files in os.walk(folder):
        for name in files:
            if os.path.splitext(name)[1].lower() in EXTS:
                paths.append(os.path.join(base, name))
    return sorted(paths)


def collect_entries(data_dir):
    """Trả (entries, has_people_dir); entries = [(khóa_người, nguồn, [đường_dẫn])]."""
    people_dir = os.path.join(data_dir, "people")
    if os.path.isdir(people_dir):
        entries = []
        for name in sorted(os.listdir(people_dir)):
            path = os.path.join(people_dir, name)
            if os.path.isdir(path):
                entries.append((name, SRC_PEOPLE, list_images(path)))
        return [e for e in entries if e[2]], True

    entries = []
    root_files = sorted(
        os.path.join(data_dir, name) for name in os.listdir(data_dir)
        if os.path.isfile(os.path.join(data_dir, name))
        and os.path.splitext(name)[1].lower() in EXTS)
    if root_files:
        entries.append((SELF, SRC_SELFIE, root_files))

    webcam_dir = os.path.join(data_dir, "real_webcam")
    if os.path.isdir(webcam_dir):
        paths = list_images(webcam_dir)
        if paths:
            entries.append((SELF, SRC_WEBCAM, paths))

    other_dir = os.path.join(data_dir, "other_people")
    if os.path.isdir(other_dir):
        for name in sorted(os.listdir(other_dir)):
            path = os.path.join(other_dir, name)
            if os.path.isdir(path):
                paths = list_images(path)
                if paths:
                    entries.append((f"other_people/{name}", SRC_STRANGER, paths))
            elif os.path.splitext(name)[1].lower() in EXTS:
                # Ảnh phẳng trong other_people/: mỗi ảnh là một người riêng.
                entries.append((f"other_people/{os.path.splitext(name)[0]}",
                                SRC_STRANGER, [path]))
    return entries, False


def embed_entries(entries):
    """rows = [(khóa_người, nguồn, tên_ảnh, embedding)], skipped = [...]."""
    rows, skipped = [], []
    for person, source, paths in entries:
        for path in paths:
            rel = os.path.basename(path)
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
            rows.append((person, source, rel, emb))
    return rows, skipped


def pair_group(person_a, src_a, person_b, src_b):
    if person_a != person_b:
        if SELF in (person_a, person_b):
            return "khac_self_nguoila"
        return "khac_nguoila_nguoila"
    if src_a == src_b == SRC_WEBCAM:
        return "cung_webcam_webcam"
    if src_a == src_b == SRC_SELFIE:
        return "cung_selfie_selfie"
    if {src_a, src_b} == {SRC_WEBCAM, SRC_SELFIE}:
        return "cung_webcam_selfie"
    return "cung_khac_nguon"


def stats(values):
    if not values:
        return None
    return {"count": len(values), "mean": sum(values) / len(values),
            "min": min(values), "max": max(values)}


def build_pairs(rows):
    groups = {}
    for (p1, s1, i1, e1), (p2, s2, i2, e2) in itertools.combinations(rows, 2):
        sim = cosine(e1, e2)
        groups.setdefault(pair_group(p1, s1, p2, s2), []).append(
            (p1, s1, i1, p2, s2, i2, sim))
    return groups


def print_group_table(groups):
    print()
    print(f"{'nhom':38s} {'so_cap':>7s} {'trung_binh':>10s} {'nho_nhat':>9s} {'lon_nhat':>9s}")
    print("-" * 78)
    for key in ("cung_webcam_webcam", "cung_webcam_selfie", "cung_selfie_selfie",
                "khac_self_nguoila", "khac_nguoila_nguoila", "cung_khac_nguon"):
        pairs = groups.get(key)
        if not pairs:
            continue
        s = stats([p[6] for p in pairs])
        print(f"{GROUP_LABELS[key]:38s} {s['count']:>7d} {s['mean']:>10.4f} "
              f"{s['min']:>9.4f} {s['max']:>9.4f}")


def _extremes(pairs, n=3):
    """Các cặp sát ngưỡng nhất: cùng người thấp nhất, khác người cao nhất."""
    low = sorted(pairs, key=lambda p: p[6])[:n]
    high = sorted(pairs, key=lambda p: p[6], reverse=True)[:n]
    return low, high


def print_extremes(groups):
    print()
    for key in ("cung_webcam_webcam", "cung_webcam_selfie"):
        pairs = groups.get(key)
        if not pairs:
            continue
        low, _ = _extremes(pairs, 3)
        print(f"{GROUP_LABELS[key]} - 3 cap thap nhat:")
        for p in low:
            print(f"  {p[2][:22]:22s} vs {p[4][:22]:22s} = {p[6]:.4f}")
    for key in ("khac_self_nguoila", "khac_nguoila_nguoila"):
        pairs = groups.get(key)
        if not pairs:
            continue
        _, high = _extremes(pairs, 3)
        print(f"{GROUP_LABELS[key]} - 3 cap cao nhat:")
        for p in high:
            print(f"  {p[2][:22]:22s} vs {p[4][:22]:22s} = {p[6]:.4f}")


def run_matcher(person, source, emb, gallery):
    """Gọi best_match thật; trả (nhận_đúng_người, similarity)."""
    got, sim = best_match(emb, gallery)
    return got, sim


def threshold_sweep(rows):
    """Quét ngưỡng bằng chính best_match (top-3 trung bình).

    Kịch bản đúng như backend:
    - Kho = ảnh webcam của chủ dự án (đăng ký bằng webcam).
    - Truy vấn webcam: leave-one-out (bỏ chính ảnh đó khỏi kho).
    - Truy vấn selfie: so với toàn bộ kho webcam.
    - Truy vấn người lạ: so với kho webcam, đúng phải là "không biết".
    """
    webcam = [(r[2], r[3]) for r in rows if r[0] == SELF and r[1] == SRC_WEBCAM]
    selfies = [(r[2], r[3]) for r in rows if r[0] == SELF and r[1] == SRC_SELFIE]
    strangers = [(r[0], r[2], r[3]) for r in rows if r[1] == SRC_STRANGER]
    if not webcam:
        print("\nKhong co anh webcam, bo qua quet nguong.")
        return []

    print()
    print("Quet nguong bang best_match that (kho = anh webcam chu du an):")
    print(f"  kho {len(webcam)} webcam | {len(selfies)} selfie | {len(strangers)} nguoi la")

    # Điểm best_match thực tế (top-3 trung bình), không phụ thuộc ngưỡng.
    old = matcher_mod.SIM_THRESHOLD
    matcher_mod.SIM_THRESHOLD = 0.0
    try:
        wc_sims = []
        for i, (_rel, emb) in enumerate(webcam):
            gallery = {SELF: [e for j, (_r2, e) in enumerate(webcam) if j != i]}
            _got, sim = best_match(emb, gallery)
            wc_sims.append(sim)
        gallery_all = {SELF: [e for _r, e in webcam]}
        sf_sims = [best_match(emb, gallery_all)[1] for _rel, emb in selfies]
        st_sims = [best_match(emb, gallery_all)[1] for _p, _r, emb in strangers]
    finally:
        matcher_mod.SIM_THRESHOLD = old
    print(f"  Diem best_match: webcam LOO {min(wc_sims):.4f}..{max(wc_sims):.4f} "
          f"(TB {sum(wc_sims) / len(wc_sims):.4f})")
    if sf_sims:
        print(f"                   selfie     {min(sf_sims):.4f}..{max(sf_sims):.4f} "
              f"(TB {sum(sf_sims) / len(sf_sims):.4f})")
    if st_sims:
        print(f"                   nguoi la   {min(st_sims):.4f}..{max(st_sims):.4f} "
              f"(TB {sum(st_sims) / len(st_sims):.4f})")

    print(f"  {'nguong':>7s} {'webcam_qua':>12s} {'selfie_qua':>12s} {'nguoi_la_vao':>13s}")
    results = []
    try:
        for t in np.round(np.arange(0.30, 0.6001, 0.02), 2):
            matcher_mod.SIM_THRESHOLD = float(t)
            wc_ok = 0
            for i, (_rel, emb) in enumerate(webcam):
                gallery = {SELF: [e for j, (_r2, e) in enumerate(webcam) if j != i]}
                got, _sim = run_matcher(SELF, SRC_WEBCAM, emb, gallery)
                wc_ok += int(got == SELF)
            sf_ok = 0
            gallery_all = {SELF: [e for _r, e in webcam]}
            for _rel, emb in selfies:
                got, _sim = run_matcher(SELF, SRC_SELFIE, emb, gallery_all)
                sf_ok += int(got == SELF)
            far = 0
            for _person, _rel, emb in strangers:
                got, _sim = run_matcher(_person, SRC_STRANGER, emb, gallery_all)
                far += int(got is not None)
            results.append((float(t), wc_ok, len(webcam), sf_ok, len(selfies),
                            far, len(strangers)))
            print(f"  {t:>7.2f} {wc_ok:>5d}/{len(webcam):<6d} "
                  f"{sf_ok:>5d}/{len(selfies):<6d} {far:>6d}/{len(strangers):<6d}")
    finally:
        matcher_mod.SIM_THRESHOLD = old
    return results


def centroid_analysis(rows):
    """So embedding TRUNG BÌNH của một lần đăng ký với từng ảnh trong kho.

    Dùng cho gợi ý ngưỡng chống đăng ký trùng khuôn mặt (không sửa backend).
    """
    webcam = [r[3] for r in rows if r[0] == SELF and r[1] == SRC_WEBCAM]
    selfies = [r[3] for r in rows if r[0] == SELF and r[1] == SRC_SELFIE]
    strangers = [(r[0], r[2], r[3]) for r in rows if r[1] == SRC_STRANGER]
    if not webcam:
        return None
    centroid = np.mean(np.asarray(webcam, dtype=np.float64), axis=0)
    same_webcam = [cosine(centroid, e) for e in webcam]
    same_selfie = [cosine(centroid, e) for e in selfies]
    same_sims = same_webcam + same_selfie
    stranger_sims = [cosine(centroid, e) for _p, _r, e in strangers]
    return {
        "same_min": min(same_sims), "same_mean": sum(same_sims) / len(same_sims),
        "same_webcam_min": min(same_webcam) if same_webcam else None,
        "same_selfie_min": min(same_selfie) if same_selfie else None,
        "stranger_max": max(stranger_sims) if stranger_sims else None,
        "stranger_mean": (sum(stranger_sims) / len(stranger_sims)
                          if stranger_sims else None),
        "n_same": len(same_sims), "n_stranger": len(stranger_sims),
    }


def main():
    parser = argparse.ArgumentParser(description="Đo cặp cùng/khác người và hiệu chỉnh ngưỡng (B3)")
    parser.add_argument("--data-dir", default=os.path.join(ROOT, "test_data"))
    parser.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "B3_pairs.csv"))
    args = parser.parse_args()

    data_dir = args.data_dir if os.path.isabs(args.data_dir) else os.path.join(ROOT, args.data_dir)
    out_path = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    if not os.path.isdir(data_dir):
        sys.exit(f"Khong thay thu muc du lieu: {data_dir}")

    entries, has_people_dir = collect_entries(data_dir)
    print(f"Du lieu: {data_dir}")
    print("Cau truc:", "people/<ten>/" if has_people_dir else "goc + real_webcam + thu muc con")
    print("So nhom:", len(entries), "| so anh:", sum(len(paths) for _p, _s, paths in entries))
    for person, source, paths in entries:
        print(f"  {source:8s} {person[:48]:48s} {len(paths)} anh")

    rows, skipped = embed_entries(entries)
    print(f"\nAnh dung duoc: {len(rows)} | bo qua: {len(skipped)}")
    for person, rel, why in skipped:
        print(f"  bo qua {person[:32]}/{rel[:24]}: {why}")
    if not rows:
        sys.exit("Khong co embedding nao, dung.")

    groups = build_pairs(rows)
    print_group_table(groups)
    print_extremes(groups)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["nhom", "nguoi_a", "nguon_a", "anh_a", "nguoi_b", "nguon_b",
                         "anh_b", "similarity"])
        for key, pairs in groups.items():
            for p1, s1, i1, p2, s2, i2, sim in pairs:
                writer.writerow([key, p1, s1, i1, p2, s2, i2, f"{sim:.6f}"])
    print("\nDa ghi:", out_path)

    sweep = threshold_sweep(rows)
    cen = centroid_analysis(rows)
    if cen:
        print("\nEmbedding trung binh cua kho webcam so voi tung anh (goi y chong trung mat):")
        print(f"  cung nguoi webcam: nho nhat {cen['same_webcam_min']:.4f}")
        print(f"  cung nguoi selfie: nho nhat {cen['same_selfie_min']:.4f}")
        print(f"  cung nguoi (tat ca {cen['n_same']} anh): nho nhat {cen['same_min']:.4f}, "
              f"trung binh {cen['same_mean']:.4f}")
        print(f"  nguoi la ({cen['n_stranger']} anh): lon nhat {cen['stranger_max']:.4f}, "
              f"trung binh {cen['stranger_mean']:.4f}")

    # Gợi ý ngưỡng: chỉ dựa trên nhóm triển khai (webcam-webcam, webcam-selfie).
    same_keys = ("cung_webcam_webcam", "cung_webcam_selfie")
    same_sims = [p[6] for k in same_keys for p in groups.get(k, [])]
    diff_sims = [p[6] for k in ("khac_self_nguoila", "khac_nguoila_nguoila")
                 for p in groups.get(k, [])]
    print()
    if same_sims and diff_sims:
        s_same, s_diff = stats(same_sims), stats(diff_sims)
        print(f"Cung nguoi (webcam-webcam + webcam-selfie): {s_same['count']} cap, "
              f"min {s_same['min']:.4f}, max {s_same['max']:.4f}")
        print(f"Khac nguoi (tat ca): {s_diff['count']} cap, "
              f"min {s_diff['min']:.4f}, max {s_diff['max']:.4f}")
        if s_same["min"] > s_diff["max"]:
            mid = (s_same["min"] + s_diff["max"]) / 2
            print(f"Tach hoan toan. Nguong giua khoang = {mid:.4f}; "
                  f"cach max khac nguoi {mid - s_diff['max']:.4f}, "
                  f"cach min cung nguoi {s_same['min'] - mid:.4f}")
            for label, t in (("giua khoang", mid), ("dang dung", matcher_mod.SIM_THRESHOLD)):
                fp = sum(1 for s in diff_sims if s >= t)
                fn = sum(1 for s in same_sims if s < t)
                print(f"  Nguong {label} {t:.4f}: FAR {fp}/{len(diff_sims)} cap, "
                      f"FRR {fn}/{len(same_sims)} cap")
        else:
            print("KHONG tach hoan toan: mien trong khong ton tai tren du lieu nay.")
    else:
        print("Thieu cap cung nguoi hoac khac nguoi de goi y nguong.")


if __name__ == "__main__":
    main()
