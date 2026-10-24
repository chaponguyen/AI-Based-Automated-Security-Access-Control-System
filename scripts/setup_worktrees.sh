#!/usr/bin/env bash
# Tạo worktree riêng cho từng Agent để chạy song song (Linux/macOS/Git Bash).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git rev-parse HEAD >/dev/null 2>&1 || { echo "Repo chưa có commit. Chạy: git add -A && git commit -m init"; exit 1; }
PARENT="$(dirname "$ROOT")"

make_wt() {  # dir branch copy_env copy_weights copy_testdata
  local path="$PARENT/$1"
  [ -d "$path" ] || git worktree add "$path" -b "$2"
  [ "$3" = 1 ] && [ -f backend/.env ] && cp backend/.env "$path/backend/.env"
  [ "$4" = 1 ] && [ -d backend/ai/weights ] && mkdir -p "$path/backend/ai/weights" && \
    cp -r backend/ai/weights/. "$path/backend/ai/weights/"
  [ "$5" = 1 ] && [ -d test_data ] && cp -r test_data "$path/"
  echo "OK: $path ($2)"
}
make_wt wt-ai agent/a1-ai 0 1 1
make_wt wt-be agent/a2-be 1 1 0
make_wt wt-fe agent/a3-fe 0 0 0
echo "Nhớ: cd ../wt-fe/frontend && npm install"
