#!/bin/sh
set -eu

cd /workspace/apps/api
python -m app.scripts.validate_deployment
python -m app.scripts.migrate
python -m app.scripts.bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
