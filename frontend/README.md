# MediRAG Frontend

Next.js chat UI over the hybrid RAG backend (Flask + Qdrant + Groq).

## Stack
- Next.js 16 (App Router, TypeScript, Turbopack)
- @supabase/supabase-js for auth + chat history
- Talks to Flask at `FLASK_API_URL` (default `http://localhost:5000`)

## Setup

1. Install deps:
   ```bash
   npm install
   ```

2. `.env.local` (already created):
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://rwkkltwkmgxlwjjdpgtt.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_NFcEx4WFfejI98aS7tCtOA_XeVrAkQq
   FLASK_API_URL=http://localhost:5000
   ```

3. Run the schema SQL once in Supabase Dashboard > SQL Editor
   (file: `D:\The LLM Workshop\supabase_schema.sql`).

4. Ensure the RAG backend is running:
   ```bash
   D:\The LLM Workshop\venv\Scripts\python.exe D:\The LLM Workshop\app.py
   ```

5. Start the dev server:
   ```bash
   npm run dev
   # http://localhost:3000
   ```

## Features
- Email/password auth (sign up + sign in) via Supabase Auth
- Chat sessions with per-user history stored in Supabase (RLS-protected)
- Ask a question → proxied server-side to Flask `/api/query`
- Hybrid retrieval sources shown per answer with expandable context

## Routes
- `/` — chat UI
- `/api/query` — server-side proxy to the Flask RAG backend
