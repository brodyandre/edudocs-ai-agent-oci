#!/usr/bin/env sh
set -eu

export EDUDOCS_ROOT_DIR="${EDUDOCS_ROOT_DIR:-/app}"
export EDUDOCS_MANIFEST_PATH="${EDUDOCS_MANIFEST_PATH:-corpus/manifest.json}"
export EDUDOCS_DOCUMENTS_DIR="${EDUDOCS_DOCUMENTS_DIR:-corpus/documents}"
export EDUDOCS_INDEX_DIR="${EDUDOCS_INDEX_DIR:-corpus/index}"
export EDUDOCS_EMBEDDING_PROVIDER="${EDUDOCS_EMBEDDING_PROVIDER:-fake}"
export EDUDOCS_LLM_PROVIDER="${EDUDOCS_LLM_PROVIDER:-${LLM_PROVIDER:-fake}}"

cd /app
python scripts/validate_corpus.py

cd /app/apps/api
if ! python -m app.ingestion.cli validate; then
  echo "Indice local ausente ou incompatível. Reconstruindo em ${EDUDOCS_INDEX_DIR}."
  python -m app.ingestion.cli build
  python -m app.ingestion.cli validate
fi

exec "$@"
