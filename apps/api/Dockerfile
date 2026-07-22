FROM python:3.10-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml apps/api/README.md ./apps/api/
COPY apps/api/app ./apps/api/app

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install ./apps/api

FROM python:3.10-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EDUDOCS_ROOT_DIR=/app \
    EDUDOCS_MANIFEST_PATH=corpus/manifest.json \
    EDUDOCS_DOCUMENTS_DIR=corpus/documents \
    EDUDOCS_INDEX_DIR=corpus/index \
    EDUDOCS_EMBEDDING_PROVIDER=fake \
    EDUDOCS_LLM_PROVIDER=fake

WORKDIR /app/apps/api

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 edudocs \
    && useradd --system --uid 10001 --gid edudocs --home-dir /app --shell /usr/sbin/nologin edudocs

COPY --from=builder /opt/venv /opt/venv
COPY --chown=edudocs:edudocs apps/api/app /app/apps/api/app
COPY --chown=edudocs:edudocs apps/api/pyproject.toml apps/api/README.md /app/apps/api/
COPY --chown=edudocs:edudocs scripts/validate_corpus.py /app/scripts/validate_corpus.py
COPY --chown=edudocs:edudocs corpus/manifest.json /app/corpus/manifest.json
COPY --chown=edudocs:edudocs corpus/documents /app/corpus/documents
COPY --chown=edudocs:edudocs corpus/sources /app/corpus/sources
COPY --chown=edudocs:edudocs corpus/evaluation/questions.json /app/corpus/evaluation/questions.json
COPY --chown=edudocs:edudocs apps/api/docker-entrypoint.sh /usr/local/bin/docker-entrypoint

RUN mkdir -p /app/corpus/index \
    && chown -R edudocs:edudocs /app \
    && chmod +x /usr/local/bin/docker-entrypoint \
    && chmod -R a-w /app/corpus/documents /app/corpus/sources /app/corpus/evaluation /app/corpus/manifest.json

USER edudocs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)); raise SystemExit(0 if data.get('status') == 'ok' else 1)"

ENTRYPOINT ["docker-entrypoint"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
