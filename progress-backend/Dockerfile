FROM python:3.12-slim

# ffmpeg is only needed when STT_PROVIDER=local. Small enough to keep either way.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

# Run pending migrations, then serve. The app refuses to start on an out-of-date
# schema, so a forgotten migration would take the site down on deploy - better to
# apply it here than to remember a manual step at 2am.
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
