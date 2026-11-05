FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_APP=app \
    FLASK_DEBUG=0

WORKDIR /app

# Metadados + código (psycopg2-binary é wheel; sem libs de build necessárias).
COPY pyproject.toml README.md LICENSE.txt ./
COPY app ./app
COPY migrations ./migrations
COPY run.py ./
COPY docker/entrypoint.sh ./docker/entrypoint.sh

RUN pip install . && chmod +x docker/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

ENTRYPOINT ["./docker/entrypoint.sh"]
