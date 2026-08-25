#!/bin/sh
set -e

echo "Applying migrations..."
alembic upgrade head

echo "Starting API..."
# One worker: background tasks live in-process, so a second worker would double
# every scheduled job. Fine well past ten users.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers \
  --forwarded-allow-ips '*'
