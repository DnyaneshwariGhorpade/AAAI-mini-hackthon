import sys
import argparse

from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Fusion, Prefetch, FusionQuery, FieldCondition, Filter, MatchValue, SparseVector,
)

QDRANT_URL = "http://localhost:6333"
COLLECTION = "healthcare_hybrid"
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SPARSE_MODEL = "Qdrant/bm25"

DENSE_TOP_K = 20
SPARSE_TOP_K = 20
FUSION_K = 8


def hybrid_search(client, dense_model, sparse_model, query, title_filter=None, dense_k=DENSE_TOP_K, sparse_k=SPARSE_TOP_K, final_k=FUSION_K):
    dense_vec = list(dense_model.embed([query]))[0].tolist()
    sp_obj = list(sparse_model.embed([query]))[0].as_object()
    sparse_vec = SparseVector(indices=sp_obj["indices"], values=sp_obj["values"])

    f = Filter(must=[FieldCondition(key="title", match=MatchValue(value=title_filter))]) if title_filter else None

    resp = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            Prefetch(query=dense_vec, using="dense", limit=dense_k, filter=f),
            Prefetch(query=sparse_vec, using="sparse", limit=sparse_k, filter=f),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=final_k,
        with_payload=True,
    )
    return resp.points

def main(query, title_filter=None, show=5):
    client = QdrantClient(url=QDRANT_URL, timeout=60)
    dense_model = TextEmbedding(DENSE_MODEL)
    sparse_model = SparseTextEmbedding(SPARSE_MODEL)

    info = client.get_collection(COLLECTION)
    print(f"Collection: {COLLECTION} | points: {info.points_count:,}\n")

    dense_vec = list(dense_model.embed([query]))[0].tolist()
    sp_obj = list(sparse_model.embed([query]))[0].as_object()
    sparse_vec = SparseVector(indices=sp_obj["indices"], values=sp_obj["values"])

    print(f"Query: {query}")
    if title_filter:
        print(f"Title filter: {title_filter}")
    print("=" * 70)

    dense_hits = client.query_points(
        collection_name=COLLECTION, query=dense_vec, using="dense",
        limit=DENSE_TOP_K, with_payload=True,
    ).points
    sparse_hits = client.query_points(
        collection_name=COLLECTION, query=sparse_vec, using="sparse",
        limit=SPARSE_TOP_K, with_payload=True,
    ).points

    print(f"\n--- DENSE-only top-{min(5, len(dense_hits))} ---")
    for p in dense_hits[:5]:
        print(f"  score={p.score:.4f} | {p.payload.get('title', '')[:80]}")
    print(f"\n--- SPARSE(BM25)-only top-{min(5, len(sparse_hits))} ---")
    for p in sparse_hits[:5]:
        print(f"  score={p.score:.4f} | {p.payload.get('title', '')[:80]}")

    fused = hybrid_search(client, dense_model, sparse_model, query, title_filter=title_filter)
    print(f"\n--- HYBRID (RRF fused) top-{min(show, len(fused))} ---")
    for i, p in enumerate(fused, 1):
        title = p.payload.get("title", "")
        text = p.payload.get("text", "")
        print(f"{i}. [score {p.score:.4f}] {title[:100]}")
        print(f"   {text[:220]}")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="*", help="query words (optional; interactive if omitted)")
    ap.add_argument("--title", default=None, help="exact title filter")
    ap.add_argument("--show", type=int, default=5)
    args = ap.parse_args()
    if args.query:
        main(" ".join(args.query), title_filter=args.title, show=args.show)
    else:
        while True:
            try:
                q = input("\nQuery> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q:
                continue
            main(q, title_filter=args.title, show=args.show)
