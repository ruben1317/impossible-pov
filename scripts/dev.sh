#!/usr/bin/env bash
set -euo pipefail
printf 'Run backend: cd backend && uvicorn app.main:app --reload --port 8000\n'
printf 'Run frontend: cd frontend && npm run dev\n'
