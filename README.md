# ✷ botforge

Multi-tenant SaaS: upload documents, get a document-grounded AI chatbot, embed it on any
website with one `<script>` tag. See `PLAN.md` for the architecture and roadmap.

**Stack:** FastAPI · PostgreSQL 16 + pgvector · Next.js 15 · fastembed (local embeddings) ·
Groq / OpenAI / Gemini / Ollama (switchable) · Docker

## Quick start (Windows)

Prereqs: Python 3.11, Node 20+, Docker Desktop **running**.

```powershell
cd C:\Users\Karti\resume\botforge
docker compose up -d                          # Postgres :5433 (pgvector) + Redis :6380
copy .env.example .env                        # then set GROQ_API_KEY and JWT_SECRET

# backend
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload --port 8000     # API docs: http://localhost:8000/docs

# frontend (new terminal)
cd C:\Users\Karti\resume\botforge\frontend
copy .env.local.example .env.local
npm run dev                                   # http://localhost:3000
```

First run downloads the local embedding model (~130 MB) the first time a document is ingested.

## Try it

1. Sign up at http://localhost:3000 → create a bot → **documents**: drop a PDF.
2. **chat**: ask questions; switch provider (groq / openai / gemini / ollama / mock) to compare answers and first-token latency.
3. **embed**: copy the script tag, or click **open demo** to see the widget on a pretend customer site.

## Comparing providers from the terminal

```powershell
cd backend
python scripts/compare_providers.py --email you@x.com --password ... --bot <bot-uuid> `
  --providers groq,gemini,mock -q "what is the refund policy?" -q "how long is shipping?"
```

Writes a CSV to `backend/scripts/out/`.

## Tests

```powershell
cd backend
pytest -q        # uses Postgres from docker compose (db botforge_test), mock LLM, hash embeddings
```

## Project layout

```
backend/app/    main · config · db · models · schemas · security
                llm/providers.py          one OpenAI-compatible client, many providers
                services/                 parsing · chunking · embeddings · ingest · retrieval (RRF) · chat (SSE)
                routers/                  auth · bots · documents · chat · public (widget, Origin allow-list)
                static/widget.js          the embeddable widget (shadow DOM, no deps)
frontend/       Next.js dashboard, "paper lab" design system (../DESIGN.md)
```
