# Healthcare RAG Hackathon — Work Plan

## 1. Project Overview

- **Domain:** Healthcare (clinical records, research literature, treatment guidelines)
- **Dataset:** 27 JSONL shards (`medical_text_shard_001.jsonl` ... `027.jsonl`), ~25 GB of medical text
- **Goal:** A RAG (Retrieval-Augmented Generation) system that answers medical questions with citations to source documents
- **Differentiator:** Hybrid retrieval (BM25 sparse + dense vector similarity) fused with RRF, on a huge domain corpus

## 2. Tech Stack

| Layer | Tool | Role |
|---|---|---|
| Frontend | **Next.js** | Chat UI, user dashboard |
| Auth + data | **Supabase** | Authentication, chat history, app DB |
| Backend | **Flask** | API, RAG orchestration, hybrid retrieval |
| Vector DB | **Qdrant** | Stores dense + sparse vectors, hybrid query, RRF fusion |
| Embeddings | **BGE-M3** (dense + sparse) or all-MiniLM + Qdrant sparse | Vectorization |
| LLM | **Groq (llama-3.3-70b)** | Answer generation (key already in `.env`) |

## 3. Architecture

```
Next.js (UI)
    │  HTTPS
    ▼
Flask API (RAG orchestration)
    │
    ├── Query → Embed (dense + sparse)
    ├── Qdrant hybrid query:
    │      prefetch dense top-k + prefetch sparse top-k
    │      → RRF fusion → top-k chunks
    ├── LLM (Groq) generation with retrieved context
    ▼
Response + citations → Next.js → saved to Supabase
```

## 4. Phases & Tasks

### Phase 0 — Data Recon (Demo Shard) [DONE NEXT]
- [ ] Download `medical_text_shard_001.jsonl` via gdown
- [ ] Inspect JSON schema (keys, text field, metadata)
- [ ] Measure record count, token length stats, language
- [ ] Detect duplicates, empty records, noise, PII risks
- [ ] Estimate total corpus size across all shards
- [ ] Decide chunk size, overlap, embedding model, metadata payloads
- **Output:** `data_schema_report.md` + locked ingestion settings

### Phase 1 — Data Prep & Chunking
- [ ] Stream-read JSONL shards (read line-by-line; never load 1 GB into memory)
- [ ] Clean: dedupe, drop empty/short, normalize whitespace
- [ ] Chunk with `RecursiveCharacterTextSplitter` (512 tokens, ~15% overlap)
- [ ] Keep provenance metadata: source shard, chunk index, text length
- [ ] Save cleaned+chunked output (parquet/jsonl) for fast re-indexing
- **Output:** cleaned chunk store, ~2-5M chunks (MVP can subsample)

### Phase 2 — Embedding & Qdrant Index
- [ ] Choose embedding model (BGE-M3 recommended: outputs dense + sparse together)
- [ ] Create Qdrant collection:
  - dense vector config (e.g., 1024-dim for BGE-M3) + sparse vector config
  - payload schema for metadata filters
- [ ] Batched upsert (500-1000 points/batch) with progress tracking
- [ ] Verify: count points, run a probe query, check latency
- **Output:** populated Qdrant collection

### Phase 3 — Hybrid Retrieval (core differentiator)
- [ ] Implement query embedding (dense + sparse)
- [ ] Qdrant `query_points` with `prefetch` (dense top-k + sparse top-k)
- [ ] **RRF fusion** (Reciprocal Rank Fusion) to merge both rankings
- [ ] Tune: `rrf_k`, per-branch top-k, optional score threshold
- [ ] Optional: reranker (bge-reranker) between retrieval and generation
- **Output:** `retrieval.py` module returning fused, ranked chunks + scores

### Phase 4 — RAG Generation (Flask core)
- [ ] Build prompt template with medical system prompt + retrieved context
- [ ] Call Groq (`llama-3.3-70b-versatile`) via existing API pattern
- [ ] Enforce: answer only from context, cite source chunks, refuse out-of-context
- [ ] Handle no-match gracefully ("I don't have enough information")
- **Output:** end-to-end RAG in a Python function

### Phase 5 — Flask API
- [ ] Endpoints:
  - `POST /api/query` — question → answer + citations + scores
  - `GET /api/health`
  - `POST /api/chat/save` / `GET /api/chat/history` (Supabase sync)
- [ ] CORS config for Next.js origin
- [ ] Error handling, request validation, timeouts
- **Output:** runnable Flask backend (`app.py`)

### Phase 6 — Next.js Frontend
- [ ] Scaffold Next.js app (App Router)
- [ ] Chat UI: message list, input, streaming response, loading states
- [ ] Display citations (source chunk previews, clickable)
- [ ] Connect to Flask API (env-configured URL)
- **Output:** working web UI

### Phase 7 — Supabase Integration
- [ ] Set up project, schema: `users`, `sessions`, `messages` (role, content, citations)
- [ ] Auth: Supabase Auth (email/Google) with Next.js client
- [ ] Save chat history per user; load history on login
- [ ] (Optional) Supabase Storage for uploaded PDFs → ingest on demand
- **Output:** authenticated, persistent chat app

### Phase 8 — Evaluation & Tuning
- [ ] Build 50-100 question eval set from the corpus (disease, drug, treatment, guideline Qs)
- [ ] Metrics: hit rate, MRR, answer faithfulness, latency
- [ ] Compare: dense-only vs sparse-only vs hybrid → show hybrid wins
- [ ] Tune chunk size, top-k, RRF weights
- **Output:** eval results table (great for the pitch deck)

### Phase 9 — Deployment & Demo
- [ ] Deploy Flask (Render/Railway), Qdrant (cloud), Next.js (Vercel), Supabase (cloud)
- [ ] Seed with a large subset (or full 25 GB if compute allows)
- [ ] Prepare demo script + pitch deck with hybrid retrieval results
- **Output:** live, demo-ready app

## 5. Suggested Timeline (e.g., 24-48h hackathon)

| Time | Milestone |
|---|---|
| H0-2 | Phase 0 (data recon) + finalize settings |
| H2-6 | Phases 1-2 (clean, chunk, embed, index) |
| H6-10 | Phase 3-4 (hybrid retrieval + generation) |
| H10-16 | Phases 5-6 (Flask API + Next.js UI) |
| H16-20 | Phase 7 (Supabase auth + history) |
| H20-24 | Phases 8-9 (evaluate, tune, deploy, pitch) |

## 6. Team Roles (4 members)

- **Member 1:** Data prep + chunking + Qdrant indexing
- **Member 2:** Hybrid retrieval + RRF fusion + reranking
- **Member 3:** Flask API + Groq generation
- **Member 4:** Next.js UI + Supabase auth/history
- **Everyone:** evaluation + demo + pitch

## 7. Existing Assets to Reuse

- `ingestion_pipeline.py` — chunking + embedding pattern (ported from ChromaDB → Qdrant)
- `Recursive_text_splitter.py` — splitter reference
- `API_call_to_llm.py` — Groq call pattern (llama-3.3-70b)
- `.env` — GROQ_API_KEY present
- `venv` — langchain, sentence-transformers, torch, transformers installed

## 8. Missing Dependencies to Install

- `qdrant-client`
- `flask`, `flask-cors`
- `rank_bm25` (if not using Qdrant sparse vectors) or BGE-M3 (`FlagEmbedding`/`sentence-transformers` with `bge-m3`)
- `supabase` (Python) + `@supabase/supabase-js` (Next.js)
- Next.js scaffolding (`create-next-app`)

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| 25 GB too large for hackathon infra | Subsample 2-5 shards for MVP; index full later |
| Embedding cost/time for full corpus | Use free local BGE-M3 or small model; batch GPU/local |
| Qdrant cloud cost | Self-host via Docker (already have Docker-friendly env) |
| Low retrieval quality | Reranker stage + hybrid fusion tuning (Phase 8) |
| Groq rate limits | Cache queries, batch, fallback model |
| Medical PII/safety | Filter PII in Phase 0; disclaimer + refusal prompt in UI |
