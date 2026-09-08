#!/usr/bin/env bash
# 백엔드와 프런트엔드를 함께 실행하는 개발용 스크립트.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ ! -d ".venv" ]; then
  echo "[YardGuard] .venv가 없습니다. README의 설치 절차를 먼저 수행하십시오."
  exit 1
fi

cleanup() {
  kill "${BACKEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT

echo "[YardGuard] 백엔드: http://localhost:8000 (문서 /docs)"
(cd backend && "$ROOT/.venv/bin/python" -m uvicorn app.main:app --port 8000) &
BACKEND_PID=$!

echo "[YardGuard] 프런트엔드: http://localhost:3000"
cd frontend && npm run dev
