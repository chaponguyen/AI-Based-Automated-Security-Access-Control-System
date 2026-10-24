"""Commit an toàn khi nhiều Agent chạy song song.

Dùng:  python scripts/agent_commit.py A2 "[B1] CP-01 mô tả - A2"

Chỉ `git add` các đường dẫn Agent được phép sửa (theo AGENTS.md) cộng với
docs/reports và docs/context (nhật ký). Không bao giờ dùng `git add -A`,
nên không commit nhầm code dở của Agent khác.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALLOWED = {
    "A1": ["backend/ai"],
    "A2": ["backend/api", "backend/services", "backend/database", "backend/migrations",
           "backend/alembic.ini", "backend/main.py", "backend/.env.example",
           "scripts/tts_probe.py"],
    "A3": ["frontend/src"],
    "A4": ["embedded"],
    "A5": ["esp32-cam"],
    "A6": ["tests"],
}
COMMON = ["docs/reports", "docs/context"]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ALLOWED:
        sys.exit('Cách dùng: python scripts/agent_commit.py <A1..A6> "<commit message>"')
    agent, msg = sys.argv[1], sys.argv[2]
    paths = [p for p in ALLOWED[agent] + COMMON if os.path.exists(os.path.join(ROOT, p))]
    r = git("add", "--", *paths)
    if r.returncode:
        sys.exit(r.stderr.strip())
    if not git("diff", "--cached", "--name-only").stdout.strip():
        print("Không có thay đổi nào trong phạm vi của", agent)
        return
    r = git("commit", "-m", msg)
    print(r.stdout.strip() or r.stderr.strip())
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
