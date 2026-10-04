# ✷ forkbot

Upload your documents, get a chatbot that answers **only** from them, and put it on any website with
one `<script>` tag. Multi-tenant: every account has its own bots, documents, chats and API keys.

**Stack:** FastAPI · PostgreSQL + pgvector (Supabase) · Next.js 15 · Gemini embeddings ·
Groq / OpenAI / Gemini for answers

## What it does

- **Ingestion** – PDF, TXT and Markdown up to 25 MB. Text is split per page / per heading section, so
  every answer cites `file.pdf · p.3`. Originals are kept (Supabase Storage or local disk) for
  download and re-indexing.
- **Retrieval** – vector similarity (pgvector, `gemini-embedding-001`) + IDF-weighted full-text
  search, fused with Reciprocal Rank Fusion. Follow-up questions are rewritten into standalone
  queries first.
- **Docs-only answers** – if nothing in the documents is close enough to the question the bot says
  so and the LLM is never called; the prompt also forbids outside knowledge.
- **Bring your own key** – users paste their own Groq / OpenAI / Gemini keys (checked, encrypted at
  rest, never shown again). With `SERVER_LLM_KEYS=false` the server's keys are never spent on chats.
- **Conversations** – stored server-side; continue old chats from the dashboard, and the widget
  remembers a visitor's chat across reloads.
- **Embeddable widget** – shadow-DOM script with no dependencies; only answers on the domains you
  allow.

## Retrieval quality

60 answerable + 12 off-topic questions written from the test documents (k = 6):

| setup | right page in top 6 | MRR | answerable refused | off-topic refused |
| --- | --- | --- | --- | --- |
| hybrid, Gemini embeddings + similarity gate (default) | 96.7 % | 0.810 | 0 % | 91.7 % |
| hybrid, local bge-small + cross-encoder gate (optional) | 91.7 % | 0.854 | 5 % | 100 % |

The default needs no local models, so the API fits in a 512 MB free instance. The local models are
still in the code, commented out (`services/embeddings.py`, `services/rerank.py`), for a bigger host.

## Running it locally

Needs Python 3.11 and Node 20+, a Postgres with pgvector (a free Supabase project works) and a
Gemini API key for embeddings ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)).

```bash
cp .env.example .env                 # DATABASE_URL, JWT_SECRET, GEMINI_API_KEY
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements.txt   # bin/ on macOS/Linux
cd backend && ../.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
cp .env.local.example .env.local
npm install && npm run dev           # http://localhost:3000
```

Database migrations run on API startup. Then: sign up → create a bot → paste an LLM key in the bot's
**settings** tab → upload a document → chat → **embed** tab → *open demo*.

## Layout

```
backend/app/        main · config · db · models · schemas · security · crypto · storage
  llm/providers.py  one OpenAI-compatible client for every provider, user keys, key checks
  services/         parsing · chunking · embeddings · ingest · retrieval · rerank · rewrite · chat
  routers/          auth · bots · documents · chat · conversations · keys · public (widget)
  static/widget.js  the embeddable widget
backend/migrations/ Alembic
frontend/           Next.js dashboard
```

---

Built by **aldol** · [dubeykartikay13@gmail.com](mailto:dubeykartikay13@gmail.com)
