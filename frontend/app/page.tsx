"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage, RAGResponse, Source } from "@/lib/types";

export default function Page() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const q = question.trim();
    if (!q || busy) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion("");
    setBusy(true);
    setError(null);

    let answer: RAGResponse;
    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      answer = await res.json();
    } catch {
      answer = { answer: "", sources: [] };
      setError("Backend unreachable. Is Flask running?");
    }

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: answer.answer || answer.error || "No answer returned.",
      sources: (answer.sources ?? []) as Source[],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, assistantMsg]);
    setBusy(false);
  }

  return (
    <main className="app">
      <header className="topbar">
        <h1>MediRAG</h1>
        <span className="subtitle">Hybrid retrieval over 120k medical abstracts (shard 01)</span>
      </header>

      <section className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <p className="empty">
              Ask a medical question about the corpus. e.g.{" "}
              <em>&quot;What is the resurgent sodium current in Purkinje neurons?&quot;</em>
            </p>
          )}
          {messages.map((m) => (
            <Message key={m.id} m={m} />
          ))}
          {busy && <p className="typing">Searching corpus…</p>}
          {error && <p className="error">{error}</p>}
          <div ref={bottomRef} />
        </div>
        <form
          className="input-row"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about shard 01 medical data…"
            autoFocus
          />
          <button className="btn primary" disabled={busy || !question.trim()}>
            Send
          </button>
        </form>
      </section>
    </main>
  );
}

function Message({ m }: { m: ChatMessage }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`msg ${m.role}`}>
      <div className="bubble">{m.content}</div>
      {m.sources && m.sources.length > 0 && (
        <button className="sources-btn" onClick={() => setOpen((v) => !v)}>
          {open ? "Hide" : "Show"} {m.sources.length} source{m.sources.length > 1 ? "s" : ""}
        </button>
      )}
      {open && m.sources && (
        <div className="sources">
          {m.sources.map((s, i) => (
            <details key={i} className="source">
              <summary>
                {i + 1}. {s.title} <span className="score">({s.score})</span>
              </summary>
              <p>{s.text}</p>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
