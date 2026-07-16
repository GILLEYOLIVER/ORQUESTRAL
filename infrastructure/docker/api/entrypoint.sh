#!/bin/sh
set -eu

cd /workspace/apps/api
alembic -c alembic.ini upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
