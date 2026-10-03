"""Run the same questions through several LLM providers against one bot and compare.

Usage (backend running, from botforge/backend with the venv active):
    python scripts/compare_providers.py --email you@x.com --password ... --bot <bot-id> \
        --providers groq,gemini,mock -q "what is the refund policy?" -q "how long is shipping?"

Prints first-token latency, total time and the answer for every provider × question,
and writes a CSV to scripts/out/compare_<timestamp>.csv.
"""
import argparse
import csv
import json
import time
from pathlib import Path

import httpx


def ask(client: httpx.Client, bot: str, provider: str, question: str) -> dict:
    t0 = time.perf_counter()
    answer, meta, err = "", {}, None
    with client.stream("POST", f"/api/bots/{bot}/chat",
                       json={"message": question, "provider": provider}, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            ev = json.loads(line[6:])
            if ev["type"] == "token":
                answer += ev["text"]
            elif ev["type"] == "done":
                meta = ev
            elif ev["type"] == "error":
                err = ev["message"]
    return {"provider": provider, "model": meta.get("model", ""), "question": question,
            "first_token_ms": meta.get("first_token_ms"), "total_ms": meta.get("total_ms") or round((time.perf_counter() - t0) * 1000),
            "answer": answer.strip(), "error": err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--bot", required=True, help="bot id (uuid) from the dashboard URL")
    ap.add_argument("--providers", default="groq,mock")
    ap.add_argument("-q", "--question", action="append", required=True)
    a = ap.parse_args()

    with httpx.Client(base_url=a.api) as c:
        c.post("/api/auth/login", json={"email": a.email, "password": a.password}).raise_for_status()
        rows = [ask(c, a.bot, p.strip(), q) for q in a.question for p in a.providers.split(",")]

    for r in rows:
        print(f"\n── {r['provider']} ({r['model']}) · first token {r['first_token_ms']} ms · total {r['total_ms']} ms")
        print(f"Q: {r['question']}")
        print(f"A: {r['error'] or r['answer'][:600]}")

    out = Path(__file__).parent / "out"
    out.mkdir(exist_ok=True)
    path = out / f"compare_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nsaved {path}")


if __name__ == "__main__":
    main()
