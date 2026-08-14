#!/usr/bin/env bash
set -euo pipefail

# Bootstrap for Railway: download shard 01 (if missing), ingest in background,
# then start the Flask API. Ingestion runs async so the healthcheck passes fast.

SHARD_ID="1__OwL8NQrRg51Vn-K9aYLCTNiwC3zBk5"
SHARD_FILE="data/raw/medical_text_shard_001.jsonl"
MAX_DOCS="${MAX_DOCS:-120000}"

mkdir -p data/raw data/state

if [ ! -f "$SHARD_FILE" ]; then
  echo "[bootstrap] downloading shard 01 ..."
  gdown --id "$SHARD_ID" -O "$SHARD_FILE"
else
  echo "[bootstrap] shard already present, skipping download"
fi

echo "[bootstrap] checking collection ..."
python - <<'PY'
import os
from qdrant_client import QdrantClient
url = os.getenv("QDRANT_URL", "http://localhost:6333")
c = QdrantClient(url=url, timeout=30)
name = os.getenv("QDRANT_COLLECTION", "healthcare_hybrid")
try:
    n = c.count(collection_name=name, exact=True).count
except Exception:
    n = 0
print(f"[bootstrap] collection '{name}' has {n} points")
print("NEEDS_INGEST=1" if n == 0 else "NEEDS_INGEST=0")
PY
NEEDS_INGEST=$(
  python - <<'PY'
import os
from qdrant_client import QdrantClient
url = os.getenv("QDRANT_URL", "http://localhost:6333")
c = QdrantClient(url=url, timeout=30)
name = os.getenv("QDRANT_COLLECTION", "healthcare_hybrid")
try:
    n = c.count(collection_name=name, exact=True).count
except Exception:
    n = 0
print("1" if n == 0 else "0")
PY
)

if [ "$NEEDS_INGEST" = "1" ]; then
  echo "[bootstrap] starting ingestion in background ..."
  nohup python ingest_qdrant.py "$SHARD_FILE" --max_docs "$MAX_DOCS" > data/state/ingest.log 2>&1 &
  echo $! > data/state/ingest.pid
else
  echo "[bootstrap] data already ingested, skipping"
fi

echo "[bootstrap] starting Flask API ..."
exec python app.py
