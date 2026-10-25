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
from ai.config import LIVENESS_MIN, LIVENESS_SEQ_MAX_FRAMES  # noqa: E402
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


# --- Cửa sổ trượt: đánh giá luật ứng viên trên toàn bộ khung của clip (B4 CP-06) ---
SLIDE_FPS = 10                 # khung/giây khi đọc clip, để cửa sổ 10-15 khung ~ 1-1,5 giây
SLIDE_LENGTHS = (10, 15)       # số khung mỗi cửa sổ
FRACTION_YS = (0.70, 0.80, 0.90)   # tỷ lệ khung đạt trong cửa sổ
STD_XS = (0.02, 0.05, 0.10, 0.15, 0.20, 0.30)

# Luật đã chốt ngày 2026-10-25 từ tập hiệu chỉnh (1 clip thật + 1 clip giả).
# Kiểm định trên clip MỚI, KHÔNG chỉnh các số này.
HOLDOUT_RULE = {"length": 15, "frac_min": 0.87, "std_max": 0.11}
HOLDOUT_FOLDERS = ("live_video_val", "spoof_video_val", "spoof_photo_val")


def read_scores(path, fps_target=SLIDE_FPS):
    """Đọc TOÀN BỘ clip trên lưới thời gian fps_target (10 khung/giây).

    Trả (scores, times, coverage, src_fps):
    - scores/times: chỉ các khung có mặt theo dõi được (IoU >= 0,3 với khung trước).
    - coverage: số khung lấy mẫu và số khung có mặt, để biết clip có bao nhiêu phần
      thực sự đánh giá được (khung không có mặt thì pipeline chặn ở bước phát hiện).
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"khong mo duoc clip: {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    step_t = 1.0 / fps_target
    next_t, idx, last_box = 0.0, 0, None
    scores, times = [], []
    samples = with_face = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = idx / src_fps if src_fps > 0 else idx
        idx += 1
        if t + 1e-6 < next_t:
            continue
        next_t += step_t          # lưới thời gian tuyệt đối, không bị trôi
        samples += 1
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
        with_face += 1
        scores.append(liveness_score(frame, last_box))
        times.append(t)
    cap.release()
    return scores, times, {"mau": samples, "co_mat": with_face}, src_fps


def windows_of(scores, times, length):
    """Các cửa sổ trượt bước 1 khung (chồng lấn, không độc lập), kèm khoảng thời gian."""
    out = []
    for i in range(len(scores) - length + 1):
        w = scores[i:i + length]
        t0, t1 = times[i], times[i + length - 1]
        out.append({
            "start": i,
            "t_start": t0,
            "t_end": t1,
            "span": t1 - t0,
            "median": float(np.median(w)),
            "frac": float(np.mean([s >= LIVENESS_MIN for s in w])),
            "std": float(np.std(w)),
        })
    return out


def _pass_rate(wins, rule):
    return sum(1 for w in wins if rule(w)) / len(wins) if wins else float("nan")


def sliding_report(root):
    """Đọc mọi clip, chấm điểm toàn bộ khung, đánh giá 3 họ luật trên cửa sổ trượt."""
    folders = [os.path.join(root, name) for name in CLIP_FOLDERS]
    data = {}          # nhom -> [(ten clip, scores)]
    for folder in folders:
        if not os.path.isdir(folder):
            print(f"  (bo qua, khong thay thu muc) {folder}")
            continue
        nhom = os.path.basename(folder)
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in VEXTS:
                continue
            try:
                scores, times, cov, src_fps = read_scores(path)
            except IOError as exc:
                print(f"  LOI {name}: {exc}")
                continue
            pct = 100.0 * cov["co_mat"] / cov["mau"] if cov["mau"] else 0.0
            print(f"  {nhom}/{name}: {src_fps:.1f} fps, lay mau {cov['mau']} khung, "
                  f"co mat {cov['co_mat']} ({pct:.0f}%), cham diem {len(scores)} khung")
            data.setdefault(nhom, []).append((name, scores, times))
    if not data:
        print("Khong co clip nao.")
        return

    real = [x for x in data.get("live_video", [])]
    spoof = [x for fam in ("spoof_photo", "spoof_video") for x in data.get(fam, [])]
    if not real or not spoof:
        print("Can it nhat 1 clip that va 1 clip gia de so sanh.")
        return

    rows = []
    for length in SLIDE_LENGTHS:
        real_w = []
        for name, scores, times in real:
            wins = windows_of(scores, times, length)
            real_w += wins
            rows += [dict(nhom="that", clip=name, L=length, **w) for w in wins]
        spoof_w = []
        for name, scores, times in spoof:
            wins = windows_of(scores, times, length)
            spoof_w += wins
            rows += [dict(nhom="gia", clip=name, L=length, **w) for w in wins]

        print(f"\n=== L={length} khung (~{length / SLIDE_FPS:.1f} giay) ===")
        print(f"  That: {len(real_w)} cua so | Gia: {len(spoof_w)} cua so "
              "(cac cua so chong lan nen KHONG doc lap)")
        if real_w:
            print("  Khoang thoi gian thuc cua cua so (that): %.2f..%.2f giay"
                  % (min(w["span"] for w in real_w), max(w["span"] for w in real_w)))
        if spoof_w:
            print("  Khoang thoi gian thuc cua cua so (gia): %.2f..%.2f giay"
                  % (min(w["span"] for w in spoof_w), max(w["span"] for w in spoof_w)))

        # (i) trung vi >= 0,60
        rule_i = lambda w: w["median"] >= LIVENESS_MIN
        pr = _pass_rate(real_w, rule_i)
        ps = _pass_rate(spoof_w, rule_i)
        print(f"  (i)  trung vi >= {LIVENESS_MIN:.2f}: that qua {100*pr:.1f}% (BPCER {100*(1-pr):.1f}%), "
              f"gia qua {100*ps:.1f}% (APCER {100*ps:.1f}%)")
        lo, hi = max(w["median"] for w in spoof_w), min(w["median"] for w in real_w)
        if hi > lo:
            print(f"       mien tach: nguong trong ({lo:.3f}; {hi:.3f}] -> giua khoang {((lo+hi)/2):.3f}, "
                  f"bien moi phia {(hi-lo)/2:.3f}")
        else:
            print(f"       KHONG tach duoc: trung vi gia cao nhat {lo:.3f} >= that thap nhat {hi:.3f}")

        # (ii) ty le khung dat >= Y%
        for y in FRACTION_YS:
            rule = lambda w, y=y: w["frac"] >= y
            pr, ps = _pass_rate(real_w, rule), _pass_rate(spoof_w, rule)
            print(f"  (ii) ty le khung dat >= {100*y:.0f}%: that qua {100*pr:.1f}% "
                  f"(BPCER {100*(1-pr):.1f}%), gia qua {100*ps:.1f}% (APCER {100*ps:.1f}%)")

        lo_f = max(w["frac"] for w in spoof_w)
        hi_f = min(w["frac"] for w in real_w)
        if hi_f > lo_f:
            print(f"       mien tach Y trong ({100*lo_f:.0f}%; {100*hi_f:.0f}%] -> "
                  f"giua khoang {100*(lo_f+hi_f)/2:.0f}%, bien moi phia {100*(hi_f-lo_f)/2:.1f} diem %")
        else:
            print(f"       KHONG tach duoc: ty le dat cao nhat cua gia {100*lo_f:.0f}% "
                  f">= thap nhat cua that {100*hi_f:.0f}%")

        # (iii) ty le dat >= Y% VA do lech chuan <= X
        feasible = []
        lo_f_all = max(w["frac"] for w in spoof_w)
        hi_f_all = min(w["frac"] for w in real_w)
        y_min = max(0.50, lo_f_all)
        y_max = min(1.00, hi_f_all)
        if y_min < y_max and y_min <= 1.0:
            for y in [y_min + (y_max - y_min) * k / 100.0 for k in range(101)]:
                spoof_pass_y = [w for w in spoof_w if w["frac"] >= y]
                if not spoof_pass_y:
                    continue
                r_max = max(w["std"] for w in real_w if w["frac"] >= y)
                s_min = min(w["std"] for w in spoof_pass_y)
                if r_max < s_min:
                    feasible.append((y, r_max, s_min))
        if feasible:
            y_lo, y_hi = feasible[0][0], feasible[-1][0]
            y_mid = (y_lo + y_hi) / 2
            best = min(feasible, key=lambda t: abs(t[0] - y_mid))
            x_mid = (best[1] + best[2]) / 2
            rule = lambda w: w["frac"] >= y_mid and w["std"] <= x_mid
            pr, ps = _pass_rate(real_w, rule), _pass_rate(spoof_w, rule)
            print(f"  (iii) ty le dat >= {100*y_mid:.0f}% VA do lech <= {x_mid:.4f}: "
                  f"that qua {100*pr:.1f}% (BPCER {100*(1-pr):.1f}%), gia qua {100*ps:.1f}% "
                  f"(APCER {100*ps:.1f}%)")
            print(f"       mien tach Y trong ({100*y_lo:.0f}%; {100*y_hi:.0f}%], "
                  f"X trong ({best[1]:.4f}; {best[2]:.4f}) -> bien Y moi phia "
                  f"{100*(y_hi-y_lo)/2:.1f} diem %, bien X moi phia {(best[2]-best[1])/2:.4f}")
        else:
            print("  (iii) KHONG co cap (Y, X) nao tach hoan toan hai nhom trong dai da thu.")

    out_path = os.path.join(ROOT, "docs", "reports", "B4_windows.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["nhom", "clip", "L", "cua_so_bat_dau", "t_bat_dau", "t_ket_thuc",
                         "do_dai_giay", "trung_vi", "ty_le_dat", "do_lech"])
        for r in rows:
            writer.writerow([r["nhom"], r["clip"], r["L"], r["start"],
                             f"{r['t_start']:.3f}", f"{r['t_end']:.3f}", f"{r['span']:.3f}",
                             f"{r['median']:.6f}", f"{r['frac']:.4f}", f"{r['std']:.6f}"])
    print("\nDa ghi:", out_path)


def _rule_test(w, rule=None):
    rule = rule or HOLDOUT_RULE
    return w["frac"] >= rule["frac_min"] and w["std"] <= rule["std_max"]


def holdout_report(root):
    """Chạy ĐÚNG luật đã chốt trên tập kiểm định, không chỉnh tham số."""
    length = HOLDOUT_RULE["length"]
    print("Luat kiem dinh (da chot, KHONG chinh): L=%d khung (~%.1f giay), "
          "ty le khung >= %.2f phai dat >= %.0f%%, do lech chuan <= %.2f"
          % (length, length / SLIDE_FPS, LIVENESS_MIN,
             100 * HOLDOUT_RULE["frac_min"], HOLDOUT_RULE["std_max"]))

    rows, summary = [], []
    for folder_name in HOLDOUT_FOLDERS:
        folder = os.path.join(root, folder_name)
        if not os.path.isdir(folder):
            print(f"  (bo qua, khong thay thu muc) {folder}")
            continue
        nhom = "that" if folder_name.startswith("live") else "gia"
        for clip in sorted(os.listdir(folder)):
            path = os.path.join(folder, clip)
            if not os.path.isfile(path) or os.path.splitext(clip)[1].lower() not in VEXTS:
                continue
            try:
                scores, times, cov, src_fps = read_scores(path)
            except IOError as exc:
                print(f"  LOI {clip}: {exc}")
                continue
            wins = windows_of(scores, times, length)
            passed = sum(1 for w in wins if _rule_test(w))
            pct = 100.0 * cov["co_mat"] / cov["mau"] if cov["mau"] else 0.0
            summary.append({
                "nhom": nhom, "clip": clip, "fps": src_fps, "mau": cov["mau"],
                "co_mat": cov["co_mat"], "pct_mat": pct, "cua_so": len(wins),
                "dat": passed,
                "frac_min": min((w["frac"] for w in wins), default=None),
                "frac_max": max((w["frac"] for w in wins), default=None),
                "std_min": min((w["std"] for w in wins), default=None),
                "std_max": max((w["std"] for w in wins), default=None),
                "span_min": min((w["span"] for w in wins), default=None),
                "span_max": max((w["span"] for w in wins), default=None),
            })
            for w in wins:
                rows.append({"nhom": nhom, "clip": clip, "pass": bool(_rule_test(w)), **w})

    if not summary:
        print("Khong co clip kiem dinh nao.")
        return

    print("\n| Nhom | Clip | Mat theo doi | Cua so | Dai cua so (s) | Ty le dat | Do lech | Cua so dat | Ket luan |")
    print("|---|---|---:|---:|---|---:|---:|---:|---|")
    for s in summary:
        if not s["cua_so"]:
            print(f"| {s['nhom']} | {s['clip']} | {s['co_mat']}/{s['mau']} | 0 | - | - | - | "
                  "0/0 | khong du cua so (chan o detect) |")
            continue
        ket = "cho qua" if s["dat"] else "chan"
        print("| %s | %s | %d/%d (%.0f%%) | %d | %.2f-%.2f | %.0f-%.0f%% | %.4f-%.4f | %d/%d | %s |"
              % (s["nhom"], s["clip"], s["co_mat"], s["mau"], s["pct_mat"], s["cua_so"],
                 s["span_min"], s["span_max"], 100 * s["frac_min"], 100 * s["frac_max"],
                 s["std_min"], s["std_max"], s["dat"], s["cua_so"], ket))

    for nhom, label in (("that", "THAT"), ("gia", "GIA")):
        group = [s for s in summary if s["nhom"] == nhom]
        total = sum(s["cua_so"] for s in group)
        passed = sum(s["dat"] for s in group)
        if total:
            rate = 100.0 * passed / total
            print(f"\n{label}: {passed}/{total} cua so duoc cho qua ({rate:.1f}%) | "
                  f"{sum(1 for s in group if s['dat'])}/{len(group)} clip co it nhat 1 cua so dat")
        else:
            print(f"\n{label}: khong co cua so nao danh gia duoc ({len(group)} clip)")

    out_path = os.path.join(ROOT, "docs", "reports", "B4_holdout.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["nhom", "clip", "cua_so_bat_dau", "t_bat_dau", "t_ket_thuc",
                         "do_dai_giay", "trung_vi", "ty_le_dat", "do_lech", "dat_luat"])
        for r in rows:
            writer.writerow([r["nhom"], r["clip"], r["start"],
                             f"{r['t_start']:.3f}", f"{r['t_end']:.3f}", f"{r['span']:.3f}",
                             f"{r['median']:.6f}", f"{r['frac']:.4f}", f"{r['std']:.6f}",
                             int(r["pass"])])
    print("\nDa ghi:", out_path)


def main():
    parser = argparse.ArgumentParser(description="Do APCER/BPCER cho chong gia mao (B4)")
    parser.add_argument("--real-dir", default=os.path.join(ROOT, "test_data", "real_webcam"))
    parser.add_argument("--spoof-dir", default=os.path.join(ROOT, "test_data", "spoof"))
    parser.add_argument("--extra-real-dir", default=os.path.join(ROOT, "test_data"),
                        help="nhom that tham khao them (mac dinh 10 selfie), de trong de bo qua")
    parser.add_argument("--out", default=os.path.join(ROOT, "docs", "reports", "B4_liveness.csv"))
    parser.add_argument("--clips", action="store_true",
                        help="che do clip: do liveness theo thoi gian tren video ngan")
    parser.add_argument("--sliding", action="store_true",
                        help="che do cua so truot: danh gia luat ung vien tren toan bo khung clip")
    parser.add_argument("--holdout", action="store_true",
                        help="chay DUNG luat da chot tren tap kiem dinh (live_video_val, spoof_video_val)")
    parser.add_argument("--clip-root", default=os.path.join(ROOT, "test_data"),
                        help="thu muc goc chua live_video/, spoof_photo/, spoof_video/")
    args = parser.parse_args()

    base = args.clip_root if os.path.isabs(args.clip_root) else os.path.join(ROOT, args.clip_root)

    if args.holdout:
        holdout_report(base)
        return

    if args.sliding:
        sliding_report(base)
        return

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
