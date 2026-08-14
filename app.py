import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq

from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Fusion, Prefetch, FusionQuery, FieldCondition, Filter, MatchValue, SparseVector,
)

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "healthcare_hybrid")
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SPARSE_MODEL = "Qdrant/bm25"
DENSE_TOP_K = 20
SPARSE_TOP_K = 20
FUSION_K = 6
GROQ_MODEL = "llama-3.3-70b-versatile"

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
SYSTEM_PROMPT = """You are a medical research assistant. Answer using ONLY the retrieved context below.
Be factual and concise. If the context does not contain enough information to answer,
say "I don't have enough information to answer your query" and nothing else.
Do not invent facts, drugs, or treatments. Where useful, cite the source title."""


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
            temperature=0.2,
            max_tokens=500,
        )
        answer = resp.choices[0].message.content
    except Exception as e:
        return jsonify({"error": f"generation failed: {e}", "sources": chunks}), 500

    return jsonify({"answer": answer, "sources": chunks})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
