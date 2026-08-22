import os
import threading
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq

from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Fusion, Prefetch, FusionQuery, FieldCondition, Filter, MatchValue, SparseVector,
    VectorParams, Distance, SparseVectorParams, SparseIndexParams,
)

from ingest_qdrant import run_ingest_worker, COLLECTION as INGEST_COLLECTION

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "data" / "state"
SHARD_ID = os.getenv("SHARD_ID", "1__OwL8NQrRg51Vn-K9aYLCTNiwC3zBk5")
SHARD_FILE = os.getenv("SHARD_FILE", "data/raw/medical_text_shard_001.jsonl")
MAX_DOCS = int(os.getenv("MAX_DOCS", "120000"))
INGEST_LOG = STATE_DIR / "ingest.log"

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "healthcare_hybrid")
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SPARSE_MODEL = "Qdrant/bm25"
DENSE_TOP_K = 30
SPARSE_TOP_K = 30
FUSION_K = 8
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

app = Flask(__name__)
CORS(app)

client = QdrantClient(url=QDRANT_URL, timeout=60)
dense_model = None
sparse_model = None
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))


def get_models():
    global dense_model, sparse_model
    if dense_model is None:
        dense_model = TextEmbedding(DENSE_MODEL)
    if sparse_model is None:
        sparse_model = SparseTextEmbedding(SPARSE_MODEL)
    return dense_model, sparse_model


def ensure_collection():
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={"dense": VectorParams(size=384, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams())},
        )


def start_ingestion():
    try:
        try:
            n = client.count(collection_name=COLLECTION, exact=True).count
        except Exception:
            n = 0
        if n > 0:
            return
        ensure_collection()
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if not Path(SHARD_FILE).exists():
            import gdown
            print("[ingest] downloading shard ...", flush=True)
            gdown.download(id=SHARD_ID, output=SHARD_FILE, quiet=True)
        with open(INGEST_LOG, "w", encoding="utf-8") as lf:
            lf.write("[ingest] starting background ingestion\n")
        dense_model, sparse_model = get_models()
        run_ingest_worker(SHARD_FILE, MAX_DOCS, client, dense_model, sparse_model,
                          log=lambda m: _log_ingest(m))
    except Exception as e:
        _log_ingest(f"[ingest] FAILED: {e!r}")


def _log_ingest(msg):
    try:
        with open(INGEST_LOG, "a", encoding="utf-8") as lf:
            lf.write(msg + "\n")
    except Exception:
        pass


threading.Thread(target=start_ingestion, daemon=True).start()
SYSTEM_PROMPT = """You are a medical research assistant that answers questions using ONLY the retrieved context below.
Strict grounding rules:
1. Every factual claim in your answer MUST be directly supported by the retrieved context, and must be followed by a citation like [n] matching the source number.
2. If a piece of information is not present in the context, do NOT use your prior knowledge to fill the gap. Omit it entirely.
3. If the context does not contain enough information to answer the question, respond with exactly: "I don't have enough information to answer your query." and nothing else.
4. Do not invent facts, drugs, dosages, years, names, or relationships. If a number or fact is not stated in the context, do not produce it.
5. Quote or closely paraphrase the source text. Keep the answer concise and factual."""


def retrieve(query, title_filter=None):
    dense_model, sparse_model = get_models()
    dense_vec = list(dense_model.embed([query]))[0].tolist()
    sp_obj = list(sparse_model.embed([query]))[0].as_object()
    sparse_vec = SparseVector(indices=sp_obj["indices"], values=sp_obj["values"])

    f = Filter(must=[FieldCondition(key="title", match=MatchValue(value=title_filter))]) if title_filter else None
    resp = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            Prefetch(query=dense_vec, using="dense", limit=DENSE_TOP_K, filter=f),
            Prefetch(query=sparse_vec, using="sparse", limit=SPARSE_TOP_K, filter=f),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=FUSION_K,
        with_payload=True,
    )
    return [
        {
            "title": p.payload.get("title", ""),
            "text": p.payload.get("text", ""),
            "score": round(p.score, 4),
            "doc_id": p.payload.get("doc_id", ""),
        }
        for p in resp.points
    ]


@app.route("/api/health", methods=["GET"])
def health():
    try:
        info = client.get_collection(COLLECTION)
        points = info.points_count
    except Exception:
        points = -1
    return jsonify({"status": "ok", "points": points, "ready": points > 0})


@app.route("/api/debug", methods=["GET"])
def debug():
    out = {}
    log_path = Path(__file__).resolve().parent / "data" / "state" / "ingest.log"
    if log_path.exists():
        lines = log_path.read_text(errors="ignore").splitlines()
        out["ingest_log_tail"] = lines[-30:]
    pid_path = Path(__file__).resolve().parent / "data" / "state" / "ingest.pid"
    if pid_path.exists():
        out["ingest_pid"] = pid_path.read_text().strip()
    out["env"] = {
        "QDRANT_URL": os.getenv("QDRANT_URL"),
        "QDRANT_COLLECTION": os.getenv("QDRANT_COLLECTION"),
        "GROQ_API_KEY": bool(os.getenv("GROQ_API_KEY")),
        "EMBED_THREADS": os.getenv("EMBED_THREADS"),
        "PORT": os.getenv("PORT"),
    }
    return jsonify(out)


@app.route("/api/query", methods=["POST"])
def query():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    title_filter = (data.get("title") or "").strip() or None
    if not question:
        return jsonify({"error": "question is required"}), 400

    try:
        chunks = retrieve(question, title_filter=title_filter)
    except Exception as e:
        return jsonify({"error": f"retrieval failed: {e}"}), 500

    if not chunks:
        return jsonify({"answer": "I don't have enough information to answer your query.", "sources": []})

    context = "\n\n".join(f"[{i+1}] ({c['title']})\n{c['text']}" for i, c in enumerate(chunks))
    try:
        resp = groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Question: {question}\n\nContext:\n{context}"},
            ],
            temperature=0.1,
            max_tokens=500,
        )
        answer = resp.choices[0].message.content
    except Exception as e:
        return jsonify({"error": f"generation failed: {e}", "sources": chunks}), 500

    return jsonify({"answer": answer, "sources": chunks})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
