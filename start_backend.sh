#!/usr/bin/env bash
set -euo pipefail

# Bootstrap for Railway: download shard 01 if missing, then start the Flask API.
# Ingestion runs in a daemon thread inside app.py so it survives as long as the app.

SHARD_ID="1__OwL8NQrRg51Vn-K9aYLCTNiwC3zBk5"
SHARD_FILE="data/raw/medical_text_shard_001.jsonl"

mkdir -p data/raw data/state

if [ ! -f "$SHARD_FILE" ]; then
  echo "[bootstrap] downloading shard 01 ..."
  gdown --id "$SHARD_ID" -O "$SHARD_FILE"
else
  echo "[bootstrap] shard already present, skipping download"
fi

echo "[bootstrap] starting Flask API ..."
exec python app.py
