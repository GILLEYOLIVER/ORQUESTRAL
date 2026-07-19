#!/bin/sh
set -eu

cd /workspace/apps/api
python -m app.scripts.validate_deployment
if [ "${RUN_MIGRATIONS_ON_STARTUP:-true}" = "true" ]; then
  python -m app.scripts.migrate
fi
python -m app.scripts.bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
