import { NextRequest, NextResponse } from "next/server";
import type { RAGResponse } from "@/lib/types";

const FLASK_URL = process.env.FLASK_API_URL || "http://localhost:5000";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  const question = (body?.question || "").toString().trim();
  const title = body?.title ? body.title.toString().trim() : null;

  if (!question) {
    return NextResponse.json({ error: "question is required" }, { status: 400 });
  }

  try {
    const res = await fetch(`${FLASK_URL}/api/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, title: title || undefined }),
      cache: "no-store",
      signal: AbortSignal.timeout(120_000),
    });

    if (!res.ok) {
      const text = await res.text();
      return NextResponse.json(
        { error: `RAG backend error (${res.status}): ${text.slice(0, 500)}` },
        { status: res.status }
      );
    }

    const data = (await res.json()) as RAGResponse;
    return NextResponse.json(data);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: `Failed to reach RAG backend at ${FLASK_URL}: ${msg}` },
      { status: 502 }
    );
  }
}
