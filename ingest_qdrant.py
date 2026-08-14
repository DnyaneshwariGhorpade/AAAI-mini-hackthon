import json
import os
import hashlib
import time
import argparse
from pathlib import Path

from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams, SparseIndexParams,
    PointStruct, CollectionStatus,
)

BASE_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parent / "data"))
RAW_DIR = BASE_DIR / "raw"
STATE_DIR = BASE_DIR / "state"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "healthcare_hybrid")
DENSE_MODEL = os.getenv("DENSE_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
SPARSE_MODEL = os.getenv("SPARSE_MODEL", "Qdrant/bm25")
THREADS = int(os.getenv("EMBED_THREADS", "12"))
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
EMBED_BATCH = 512
FLUSH_EVERY = 5000          # docs to buffer before embedding+upsert


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunk = text[start:end]
        if end < len(text):
            split_at = max(chunk.rfind(". "), chunk.rfind("? "), chunk.rfind("! "),
                           chunk.rfind("; "), chunk.rfind(", "), chunk.rfind(" "))
            if split_at > int(size * 0.5):
                chunk = chunk[: split_at + 1]
                end = start + split_at + 1
        chunks.append(chunk.strip())
        if end >= len(text):
            break
        start = end - overlap
    return [c for c in chunks if c]


def state_file(shard_name):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / (shard_name + ".progress")


def read_state(shard_name):
    sf = state_file(shard_name)
    if sf.exists():
        return int(sf.read_text().strip())
    return 0


def main(shard_path, max_docs=0, recreate=False):
    shard_path = Path(shard_path)
    if not shard_path.exists():
        raise FileNotFoundError(shard_path)

    client = QdrantClient(url=QDRANT_URL, timeout=120)
    if recreate or not client.collection_exists(COLLECTION):
        if client.collection_exists(COLLECTION):
            client.delete_collection(COLLECTION)
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={"dense": VectorParams(size=384, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams())},
        )
        print("collection created", flush=True)

    dense_model = TextEmbedding(DENSE_MODEL, threads=THREADS)
    sparse_model = SparseTextEmbedding(SPARSE_MODEL, threads=THREADS)
    run_ingest_worker(shard_path, max_docs, client, dense_model, sparse_model)


def run_ingest_worker(shard_path, max_docs, client, dense_model, sparse_model, log=print):
    """Core ingestion loop, callable from a thread so it shares the parent process's models."""
    shard_path = Path(shard_path)
    if not shard_path.exists():
        raise FileNotFoundError(shard_path)
    shard_name = shard_path.name

    start_line = read_state(shard_name)
    points = []
    total_upserted = client.count(collection_name=COLLECTION, exact=True).count
    t0 = time.time()

    with open(shard_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < start_line:
                continue
            if max_docs and (i - start_line) >= max_docs:
                break
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = (doc.get("text") or "").strip()
            if not text:
                continue
            for ci, chunk in enumerate(chunk_text(text)):
                pid = hashlib.md5(f"{doc.get('doc_id')}_{ci}_{chunk[:64]}".encode()).hexdigest()
                points.append({
                    "id": pid,
                    "doc_id": doc.get("doc_id"),
                    "title": doc.get("title", ""),
                    "text": chunk,
                    "chunk_index": ci,
                    "source": shard_name,
                })

            if len(points) >= FLUSH_EVERY:
                _flush(client, dense_model, sparse_model, points)
                total_upserted += len(points)
                points = []
                state_file(shard_name).write_text(str(i + 1))
                log(f"  line {i+1:,}: upserted {total_upserted:,} chunks total "
                    f"({time.time()-t0:.0f}s)")

    if points:
        _flush(client, dense_model, sparse_model, points)
        total_upserted += len(points)
        state_file(shard_name).write_text(str(0))  # reset -> shard done

    client.update_collection(collection_name=COLLECTION, wait=True)
    while client.get_collection(COLLECTION).status != CollectionStatus.GREEN:
        time.sleep(1)
    info = client.get_collection(COLLECTION)
    log(f"DONE. Collection points: {info.points_count:,} in {time.time()-t0:.0f}s")


def _flush(client, dense_model, sparse_model, points):
    texts = [p["text"] for p in points]
    dense = list(dense_model.embed(texts, batch_size=EMBED_BATCH))
    sparse = list(sparse_model.embed(texts, batch_size=EMBED_BATCH))
    upsert = [
        PointStruct(
            id=p["id"],
            vector={"dense": d.tolist(), "sparse": s.as_object()},
            payload={k: v for k, v in p.items() if k != "id"},
        )
        for p, d, s in zip(points, dense, sparse)
    ]
    for i in range(0, len(upsert), 1000):
        client.upsert(collection_name=COLLECTION, points=upsert[i:i + 1000], wait=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("shard_path")
    ap.add_argument("--max_docs", type=int, default=0)
    ap.add_argument("--recreate", action="store_true")
    args = ap.parse_args()
    main(args.shard_path, args.max_docs, args.recreate)
