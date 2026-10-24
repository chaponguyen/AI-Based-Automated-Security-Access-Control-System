#!/usr/bin/env python3
"""Ghi nhật ký checkpoint ngay sau mỗi bước, kèm dòng code đã viết.

Ghi một checkpoint (chạy TRƯỚC khi git commit để --auto thấy đúng phần vừa sửa):
  python scripts/log_checkpoint.py B1 CP-02 --file backend/database/models.py --auto \
      --did "Bảng users: cột status + CheckConstraint, created_at" \
      --why "status chỉ nhận active/inactive" --check "py_compile OK" --todo "CP-03 face_embeddings"

Ghi bàn giao khi sắp hết token/quota:
  python scripts/log_checkpoint.py B1 --handoff --note "Đang dở CP-03, models.py dòng 40-52, còn thiếu cột embedding"
"""
import argparse, datetime, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
now = lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

def merge(ranges):
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in out)

def auto_lines(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return "(không tìm thấy file)"
    diff = subprocess.run(["git", "diff", "-U0", "HEAD", "--", path], cwd=ROOT,
                          capture_output=True, text=True).stdout
    rs = []
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        start, cnt = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
        if cnt > 0:
            rs.append((start, start + cnt - 1))
    if not rs:  # file mới chưa commit, hoặc không có thay đổi so với HEAD
        n = sum(1 for _ in open(full, encoding="utf-8", errors="ignore"))
        rs = [(1, max(n, 1))]
    return merge(rs)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task"); ap.add_argument("cp", nargs="?")
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--lines"); ap.add_argument("--auto", action="store_true")
    ap.add_argument("--did"); ap.add_argument("--why", default="-")
    ap.add_argument("--check", default="-"); ap.add_argument("--todo", default="-")
    ap.add_argument("--handoff", action="store_true"); ap.add_argument("--note")
    a = ap.parse_args()

    rep = os.path.join(ROOT, "docs", "reports", f"{a.task}.md")
    if not os.path.exists(rep):
        sys.exit(f"Không có {rep}. Kiểm tra mã việc (ví dụ B1).")
    text = open(rep, encoding="utf-8").read()
    prog = os.path.join(ROOT, "docs", "context", "PROGRESS_LOG.md")

    if a.handoff:
        if not a.note: sys.exit("Thiếu --note")
        entry = f"\n### {now()}\n{a.note}\n"
        text = text.replace("## Bàn giao khi bị ngắt\n", "## Bàn giao khi bị ngắt\n" + entry, 1)
        line = f"- {now()} [{a.task}] BÀN GIAO: {a.note}\n"
    else:
        if not (a.cp and a.did and a.file): sys.exit("Cần CP, --file và --did")
        where = []
        for f in a.file:
            ln = a.lines if (a.lines and not a.auto) else auto_lines(f)
            where.append(f"`{f}` dòng {ln}")
        entry = (f"\n### {a.cp} · {now()}\n- File: {'; '.join(where)}\n- Đã làm: {a.did}\n"
                 f"- Giải thích: {a.why}\n- Kiểm tra: {a.check}\n- Bước kế tiếp: {a.todo}\n")
        text = text.replace(f"- [ ] {a.cp} ", f"- [x] {a.cp} ", 1)
        text = text.rstrip("\n") + "\n"
        marker = "\n## Bàn giao khi bị ngắt"
        if marker in text:
            text = text.replace(marker, entry + marker, 1)
        else:
            text += entry
        line = f"- {now()} [{a.task}] {a.cp} ({'; '.join(a.file)}): {a.did}\n"

    open(rep, "w", encoding="utf-8").write(text)
    with open(prog, "a", encoding="utf-8") as fh:
        fh.write(line)
    print("Đã ghi:", line.strip())

if __name__ == "__main__":
    main()
