# BotForge: Implementation Plan

> Multi-tenant SaaS where users upload documents and deploy an embeddable AI chatbot
> on any website with one `<script>` tag.

**Centre of gravity:** multi-tenancy, SaaS infrastructure, production engineering.
**UI:** follows `../DESIGN.md` ("paper lab").

## 1. Architecture

```
 ┌───────────── Next.js dashboard (:3000) ─────────────┐        ┌── any website ──┐
 │ /login /signup /bots /bots/[id] (upload·chat·embed) │        │ <script src=    │
 └──────────────┬──────────────────────────────────────┘        │  widget.js>     │
                │ /api/* (rewrite → same origin, httpOnly cookie)└───────┬────────┘
                ▼                                                        │ /public/* (Origin allow-list)
 ┌──────────────────────────── FastAPI (:8000) ────────────────────────────┐
 │ routers: auth · bots · documents · chat · public · providers            │
 │ services: ingest (parse→chunk→embed) · retrieval (vector+FTS→RRF)       │
 │ llm/: provider registry → groq | openai | gemini | ollama | mock        │
 │ embeddings/: fastembed (local) | openai | hash (tests)                  │
 └─────┬───────────────────────────────┬───────────────────────────────────┘
       ▼                               ▼
 PostgreSQL 16 + pgvector        Redis 7 (phase 2: rate limits, Celery broker)
```

## 2. Folder layout

```
botforge/
├── PLAN.md  README.md  docker-compose.yml  .env.example
├── .venv/                       ← Python 3.11 venv (backend only)
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py  config.py  db.py  models.py  schemas.py  security.py
│   │   ├── llm/          providers.py (OpenAI-compatible client per provider)
│   │   ├── services/     embeddings.py  chunking.py  parsing.py  ingest.py  retrieval.py  chat.py
│   │   ├── routers/      auth.py  bots.py  documents.py  chat.py  public.py  providers.py
│   │   └── static/       widget.js
│   ├── scripts/          compare_providers.py  eval_retrieval.py (phase 2)
│   └── tests/            test_auth.py  test_ingest.py  test_retrieval.py  test_public.py
└── frontend/             Next.js 15 (App Router, TypeScript, plain CSS modules)
    └── app/  components/  lib/api.ts  public/
```

## 3. Data model (Postgres)

| Table | Key columns |
| --- | --- |
| `users` | id, email (unique), password_hash (bcrypt), created_at |
| `bots` | id, owner_id → users, name, public_id (random, used by widget), system_prompt, llm_provider, llm_model, allowed_domains text[], created_at |
| `documents` | id, bot_id, owner_id, filename, status (`pending/processing/ready/failed`), error, n_chunks, created_at |
| `chunks` | id, bot_id, owner_id, document_id, ord, content, embedding vector(384), tsv tsvector (generated), HNSW index on embedding, GIN on tsv |
| `messages` (phase 2) | id, bot_id, session_id, role, content, latency_ms, tokens |

`owner_id` is denormalised onto every row so Row-Level Security policies (phase 2)
are a single `owner_id = current_setting('app.user_id')::uuid` predicate.

## 4. API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/auth/signup` · `/api/auth/login` · `/api/auth/logout` | – | sets httpOnly JWT cookie |
| GET | `/api/auth/me` | cookie | current user |
| GET/POST | `/api/bots` | cookie | list / create |
| GET/PATCH/DELETE | `/api/bots/{id}` | cookie | settings: prompt, provider, model, allowed domains |
| POST | `/api/bots/{id}/documents` | cookie | multipart upload (pdf/txt/md, ≤ 10 MB) → background ingest |
| GET | `/api/bots/{id}/documents` | cookie | list with status |
| POST | `/api/bots/{id}/chat` | cookie | SSE stream; body may override `provider`/`model` for testing |
| GET | `/api/providers` | cookie | which providers are configured (key present) |
| GET | `/widget.js` | – | embeddable script |
| GET | `/public/bots/{public_id}` | Origin | bot name/greeting for widget |
| POST | `/public/bots/{public_id}/chat` | Origin | SSE stream for widget |

SSE events: `{"type":"token","text":…}` · `{"type":"sources","items":[…]}` ·
`{"type":"done","first_token_ms":…,"total_ms":…,"provider":…,"model":…}` · `{"type":"error",…}`

## 5. Key designs

**Multi-provider LLM.** Groq, OpenAI, Gemini and Ollama all expose OpenAI-compatible
chat endpoints, so one client class with a per-provider `base_url` + key + default model.
`mock` is an offline provider that streams an extractive answer from the retrieved chunks:
used in tests and when no key is set. Provider resolution: request override → bot setting →
`DEFAULT_LLM_PROVIDER`. `scripts/compare_providers.py` runs the same questions through every
configured provider and prints first-token latency, total time and answers side by side.

**Hybrid retrieval.** Top-k by cosine distance (`<=>`) and top-k by `ts_rank_cd` on
`websearch_to_tsquery`, fused with Reciprocal Rank Fusion: `score = Σ 1/(60 + rank)`.
Both queries are filtered by `bot_id` (and `owner_id`).

**Widget security.** `public_id` is unguessable but public, so the real control is the
**Origin allow-list**: `/public/*` reads the `Origin` header, matches it against
`allowed_domains` (exact host or `*.example.com`), and only then returns CORS headers.
New bots default to `localhost`. Phase 2 adds Redis token-bucket limits per bot + per IP.

**Ingestion.** `pypdf` → normalise whitespace → recursive chunking (~800 chars, 120 overlap,
split on paragraphs then sentences) → batch embed → bulk insert. MVP runs in FastAPI
`BackgroundTasks`; phase 2 moves it to Celery so the API stays stateless.

## 6. Build steps

### Phase 1 (MVP): signup → upload PDF → chat → embed widget
1. [x] Config, DB engine, models, `create_all` + `CREATE EXTENSION vector`
2. [x] Auth: bcrypt, JWT cookie, `get_current_user` dependency
3. [x] Bots CRUD with owner scoping
4. [x] Upload + ingest pipeline + document status
5. [x] Embedding providers (fastembed / hash) and hybrid retrieval with RRF
6. [x] Provider registry + SSE chat endpoint (+ per-request override)
7. [x] Public API with Origin allow-list + `widget.js`
8. [x] Tests (pytest, `mock` LLM, `hash` embeddings, real Postgres)
9. [x] Next.js: layout + design tokens, auth pages, bots list, bot page (docs · chat · embed · settings)
10. [x] `compare_providers.py`, README, Windows `.venv` + `npm install`

### Phase 2 (resume bullets)
1. Row-Level Security: non-superuser app role, `SET LOCAL app.user_id` per request, policies on all tables, test that a cross-tenant query returns 0 rows
2. Celery worker for ingestion (Redis broker)
3. Redis token-bucket rate limit + monthly message quota per tenant
4. Messages table + analytics page (volume, first-token p50/p95, top questions)
5. Eval set (`[N]` Q&A pairs) → measure vector-only vs hybrid hit-rate → fill `[X]%`
6. GitHub Actions: lint, pytest, retrieval eval gate; Dockerfiles; Railway deploy

## 7. Running locally (Windows)

```powershell
cd C:\Users\Karti\resume\botforge
docker compose up -d                       # Postgres :5433, Redis :6380 (start Docker Desktop first)
copy .env.example .env                     # add GROQ_API_KEY
.\.venv\Scripts\Activate.ps1
cd backend; uvicorn app.main:app --reload  # http://localhost:8000/docs
# new terminal
cd ..\frontend; npm run dev                # http://localhost:3000
```

## 8. Resume-bullet → evidence map

| Bullet | Where it's proven | Number to measure |
| --- | --- | --- |
| Embeddable widget + domain allow-listing | `public.py`, `widget.js`, `test_public.py` | – |
| RLS isolation + hybrid RRF retrieval | phase 2 RLS migration, `retrieval.py`, `eval_retrieval.py` | accuracy gain `[X]%` on `[N]` questions |
| Quotas, rate limiting, SSE, Celery | phase 2 | first token `[X] ms` (logged in `done` event) |
| Docker + CI/CD | phase 2 | – |
