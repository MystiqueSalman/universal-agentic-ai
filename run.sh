#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8100 --app-dir backend
