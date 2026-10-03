"""Retrieval eval: how often does search put the right page in front of the LLM?

    cd backend
    python scripts/eval_retrieval.py ../test-docs/pdf/01-pre.pdf ... -q eval/questions.jsonl

Indexes the files into a throwaway bot (local Docker Postgres database `forkbot_eval` by default),
then for every question in the eval set compares:

    vector          pgvector cosine only
    keyword         IDF-weighted full-text only
    hybrid          both, fused with RRF
    hybrid+rerank   + cross-encoder re-rank and the relevance gate (what the app runs)

Metrics (k = RETRIEVAL_K): hit@k by page (strict) and by file (lenient), MRR by page, and for the
gated mode the false-refusal rate on answerable questions and the refusal rate on off-topic ones.
Writes a JSON report to scripts/out/.
"""
import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://forkbot:forkbot@localhost:5433/forkbot_eval")


def ensure_local_database(url_str: str, allow_remote: bool) -> None:
    import psycopg
    from sqlalchemy.engine import make_url

    url = make_url(url_str)
    if url.host not in ("localhost", "127.0.0.1", "::1") and not allow_remote:
        raise SystemExit(f"refusing to write eval data to {url.host!r}; pass --allow-remote to override")
    admin = url.set(database="postgres", drivername="postgresql")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (url.database,)).fetchone():
            c.execute(f'CREATE DATABASE "{url.database}"')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-q", "--questions", default="eval/questions.jsonl")
    ap.add_argument("--allow-remote", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the throwaway bot (re-run without re-indexing: --bot)")
    ap.add_argument("--bot", help="reuse an already indexed eval bot id")
    args = ap.parse_args()
    ensure_local_database(os.environ["DATABASE_URL"], args.allow_remote)

    from app.config import get_settings
    from app.db import SessionLocal, init_db
    from app.models import Bot, Document, User
    from app.services.ingest import ingest_document
    from app.services.retrieval import retrieve

    init_db()
    k = get_settings().retrieval_k
    questions = [json.loads(line) for line in Path(args.questions).read_text(encoding="utf-8").splitlines() if line.strip()]

    with SessionLocal() as db:
        if args.bot:
            bot = db.get(Bot, uuid.UUID(args.bot))
        else:
            user = User(email=f"eval-{uuid.uuid4().hex[:8]}@forkbot.local", password_hash="!")
            db.add(user)
            db.flush()
            bot = Bot(owner_id=user.id, name="eval")
            db.add(bot)
            db.commit()
            t = time.perf_counter()
            for f in args.files:
                doc = Document(bot_id=bot.id, owner_id=user.id, filename=Path(f).name, size_bytes=os.path.getsize(f))
                db.add(doc)
                db.commit()
                ingest_document(doc.id, Path(f).read_bytes())
            print(f"indexed {len(args.files)} files in {time.perf_counter() - t:.1f}s (bot {bot.id})")
        bot_id, owner_id = bot.id, bot.owner_id

    modes = {"vector": ("vector", False), "keyword": ("keyword", False),
             "hybrid": ("hybrid", False), "hybrid+rerank": ("hybrid", True)}
    report = {}
    with SessionLocal() as db:
        retrieve(db, bot_id, "warm up the models")
        for name, (mode, rerank) in modes.items():
            page_hits = file_hits = refused_in = refused_out = 0
            rr, ms, n_in, n_out = 0.0, [], 0, 0
            for item in questions:
                t = time.perf_counter()
                hits = retrieve(db, bot_id, item["q"], k=k, mode=mode, rerank=rerank)
                ms.append((time.perf_counter() - t) * 1000)
                if item["type"] == "out":
                    n_out += 1
                    refused_out += not hits
                    continue
                n_in += 1
                refused_in += not hits
                match = [i for i, h in enumerate(hits, 1) if h.filename == item["file"]
                         and h.page == item["page"] and (item["section"] is None or h.section == item["section"])]
                page_hits += bool(match)
                file_hits += any(h.filename == item["file"] for h in hits)
                rr += 1 / match[0] if match else 0
            report[name] = {
                f"hit@{k}_page": round(page_hits / n_in, 3), f"hit@{k}_file": round(file_hits / n_in, 3),
                "mrr_page": round(rr / n_in, 3), "avg_ms": round(sum(ms) / len(ms)),
                **({"false_refusal_in_scope": round(refused_in / n_in, 3),
                    "refusal_off_topic": round(refused_out / n_out, 3)} if rerank else {}),
            }

    print(f"\n{len(questions)} questions ({n_in} answerable, {n_out} off-topic), k={k}\n")
    cols = [f"hit@{k}_page", f"hit@{k}_file", "mrr_page", "false_refusal_in_scope", "refusal_off_topic", "avg_ms"]
    print(f"{'mode':15}" + "".join(f"{c:>24}" for c in cols))
    for name, r in report.items():
        print(f"{name:15}" + "".join(f"{str(r.get(c, '–')):>24}" for c in cols))

    out = Path(__file__).parent / "out"
    out.mkdir(exist_ok=True)
    path = out / f"eval_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps({"k": k, "n_questions": len(questions), "results": report}, indent=2), encoding="utf-8")
    print(f"\nreport: {path}")

    if not args.keep and not args.bot:
        with SessionLocal() as db:
            db.delete(db.get(User, owner_id))
            db.commit()


if __name__ == "__main__":
    main()
