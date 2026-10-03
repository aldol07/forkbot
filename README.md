# ✷ forkbot

Upload your documents, get a chatbot that answers **only** from them, and put it on any website with
one `<script>` tag. Multi-tenant: every account has its own bots, documents, chats and API keys.

**Stack:** FastAPI · PostgreSQL 16 + pgvector (Supabase or Docker) · Next.js 15 · fastembed (local
embeddings + cross-encoder re-ranker) · Groq / OpenAI / Gemini / Ollama · Docker

## What it does

- **Ingestion** – PDF, TXT and Markdown up to 25 MB. Text is split per page / per heading section, so
  every answer cites `file.pdf · p.3`. Originals are kept (local disk or any S3-compatible bucket) for
  download and re-indexing.
- **Retrieval** – pgvector similarity + IDF-weighted full-text search, fused with Reciprocal Rank
  Fusion, then re-ranked by a cross-encoder. Follow-up questions are rewritten into standalone
  queries first.
- **Docs-only answers** – if no passage clears the re-ranker threshold the bot says so and the LLM
  is never called. On the eval set every off-topic question was refused.
- **Bring your own key** – users paste their own Groq / OpenAI / Gemini keys (checked, encrypted at
  rest, never shown again). The server's keys are an optional fallback (`SERVER_LLM_KEYS`).
- **Conversations** – stored server-side; continue old chats from the dashboard, and the widget
  remembers a visitor's chat across reloads.
- **Embeddable widget** – shadow-DOM script with no dependencies; only answers on the domains you
  allow.

## Retrieval quality

`backend/scripts/eval_retrieval.py` on 60 answerable + 12 off-topic questions (k = 6):

| mode | right page in top 6 | MRR | off-topic refused |
| --- | --- | --- | --- |
| vector only | 95.0 % | 0.762 | – |
| keyword only | 93.3 % | 0.751 | – |
| hybrid (RRF) | 98.3 % | 0.828 | – |
| hybrid + re-rank + gate | 91.7 % | **0.854** | **100 %** |

## Running it locally

Needs Python 3.11, Node 20+ and Docker.

```bash
docker compose up -d                 # Postgres + pgvector on :5433
cp .env.example .env                 # set JWT_SECRET; add a provider key or paste one in the UI later
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements.txt   # bin/ on macOS/Linux
cd backend && ../.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
cp .env.local.example .env.local
npm install && npm run dev           # http://localhost:3000
```

Windows users can run `setup.ps1` for the venv + npm steps. The embedding and re-ranker models
(~210 MB) download on first use. Database migrations run on API startup.

Then: sign up → create a bot → upload a document → chat → **embed** tab → *open demo* to see the
widget on a sample page.

## Tests

```bash
cd backend && ../.venv/Scripts/python -m pytest -q
```

Uses the Docker Postgres (`forkbot_test` database), a mock LLM and hash embeddings, so no keys or
model downloads are needed. The suite refuses to run against a non-local database.

## Deploying for free

- **Database + files:** Supabase (pgvector is built in; migrations enable RLS on every table, so the
  Data API can't read them).
- **API:** `backend/Dockerfile` (models baked in) on Hugging Face Spaces, Render or similar.
- **Dashboard:** Vercel with root directory `frontend`, `BACKEND_URL` and `NEXT_PUBLIC_API_URL`
  pointing at the API.
- Set `SERVER_LLM_KEYS=false` so users bring their own keys, `COOKIE_SECURE=true`, and a long
  `JWT_SECRET`.

## Layout

```
backend/app/        main · config · db · models · schemas · security · crypto · storage
  llm/providers.py  one OpenAI-compatible client for every provider, user keys, key checks
  services/         parsing · chunking · embeddings · ingest · retrieval · rerank · rewrite · chat
  routers/          auth · bots · documents · chat · conversations · keys · public (widget)
  static/widget.js  the embeddable widget
backend/migrations/ Alembic
backend/scripts/    eval_retrieval · make_eval_set · compare_providers
frontend/           Next.js dashboard
```

---

Built by **aldol** · [dubeykartikay13@gmail.com](mailto:dubeykartikay13@gmail.com)
