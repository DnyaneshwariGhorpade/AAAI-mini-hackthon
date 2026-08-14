# RAG Pipeline Build Report

**Date:** 2026-08-14
**Project:** Healthcare RAG Hackathon
**Dataset:** `medical_text_shard_001.jsonl` (Google Drive, 1.07 GB)

---

## 1. What Was Built

A complete, working RAG (Retrieval-Augmented Generation) pipeline using the agreed stack:

| Layer | Tool | Status |
|---|---|---|
| Vector DB | **Qdrant** (self-hosted binary, v1.19.0, port 6333) | ✅ Running |
| Embeddings (dense) | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) via fastembed | ✅ |
| Embeddings (sparse/BM25) | `Qdrant/bm25` via fastembed | ✅ |
| Hybrid fusion | Qdrant prefetch (dense + sparse) → **RRF** (Reciprocal Rank Fusion) | ✅ |
| Backend API | **Flask** (port 5000) | ✅ Running |
| LLM | **Groq** `llama-3.3-70b-versatile` | ✅ |

---

## 2. Files Created

| File | Purpose |
|---|---|
| `ingest_qdrant.py` | Streams JSONL → chunks → dense+sparse vectors → upserts to Qdrant (resumable, checkpointed) |
| `query_hybrid.py` | CLI hybrid search: dense-only / sparse-only / RRF-fused comparison |
| `app.py` | Flask API: `/api/health`, `/api/query` (hybrid retrieval + Groq generation) |
| `data/shards_manifest.tsv` | All 27 shard file IDs from Drive |
| `data/state/ingest.log` | Live ingestion progress log |

---

## 3. Data Model

**JSONL schema** (verified from shard 001):
- `doc_id` — unique string, e.g. `med_doc_00000000`
- `title` — question/statement title (median 61 chars)
- `text` — abstract/paragraph (median 245 chars, mean 795, max 17,904)

**Qdrant collection:** `healthcare_hybrid`
- 2 named vectors per point: `dense` (384-dim, COSINE) + `sparse` (BM25)
- Payload: `doc_id`, `title`, `text`, `chunk_index`, `source` (shard filename)
- Chunking: ~1000 chars, ~150 overlap, sentence-boundary aware

---

## 4. Verification Results

### Query 1: "What is the resurgent sodium current in cerebellar Purkinje neurons?"
- Dense-only top hit: correct abstract (score 0.77)
- Sparse-only top hit: correct abstract (score 16.5)
- **Hybrid RRF top-2: both correct** (0.83 each)
- LLM answer: accurate, cited summary of the FGF14/resurgent NaV finding

### Query 2: "What causes epileptic encephalopathy?"
- Correct: SCN8A de novo mutations, with source citation

### Title filter test
- Results correctly restricted to the exact matching title

---

## 5. Current Ingestion Status

- **40,000+ chunks** indexed from shard 001 (of 120k-doc demo cap) — running in background
- Throughput: **~57 chunks/sec** (dense embedding is the bottleneck on this CPU, Ryzen 5 8640U)

---

## 6. Performance Notes & Constraints

- Dense embedding runs at **~60 docs/s** on CPU. The full 25 GB corpus (~30M chunks) would take roughly **140 hours** to index on this machine alone.
- **Recommendation for the hackathon:** index a representative subset for the demo (e.g. 2-3 shards), and if the full corpus is required, use GPU-based embedding (local GPU or cloud) or a smaller/quantized dense model.
- Upsert payload limit (32 MB) handled by sub-batching at 1000 points.
- Qdrant is a standalone Windows binary (no Docker needed); restart with `qdrant.exe` if rebooted.

---

## 7. How to Run

```bash
# 1. Qdrant (already running; restart after reboot from D:\The LLM Workshop\qdrant)
& "D:\The LLM Workshop\qdrant\qdrant.exe"

# 2. Ingest a shard
.\venv\Scripts\python.exe ingest_qdrant.py "data\raw\medical_text_shard_001.jsonl" --recreate

# 3. CLI hybrid test
.\venv\Scripts\python.exe query_hybrid.py "your medical question here"

# 4. Flask API
.\venv\Scripts\python.exe app.py
# POST http://localhost:5000/api/query  {"question": "..."}
```

---

## 8. Next Steps (pending data-cleaning decision)

1. **Wait for demo ingestion to finish** (~120k docs) — then decide whether to scale to more shards
2. **Stream full dataset**: download remaining 26 shards → ingest → delete raw (to respect 16 GB disk limit)
3. If time allows: data cleaning (dedupe, empty/short filters, normalization) as a pre-ingest step
4. Next.js frontend + Supabase auth/history integration
