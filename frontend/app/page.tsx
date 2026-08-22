import Link from "next/link";

export default function Page() {
  return (
    <main className="welcome">
      <div className="welcome-card">
        <div className="badge">Medical RAG Chatbot</div>
        <h1>MediRAG</h1>
        <p className="tagline">
          Ask medical questions and get answers grounded in 92k research
          abstracts — retrieved with hybrid dense + sparse search and answered
          strictly from cited sources.
        </p>
        <ul className="features">
          <li>Hybrid retrieval (dense embeddings + BM25 sparse) with RRF fusion</li>
          <li>Answers cite the exact abstracts they came from</li>
          <li>No sign-up needed — just ask</li>
        </ul>
        <Link href="/chat" className="btn primary start-btn">
          Start Q&amp;A Session
        </Link>
        <p className="disclaimer">
          For research demonstration only — not medical advice.
        </p>
      </div>
    </main>
  );
}
