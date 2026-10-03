"""Generate the retrieval eval set: one natural question per PDF page / Markdown section.

    cd backend
    python scripts/make_eval_set.py ../test-docs/pdf/01-pre.pdf ../test-docs/md/guide.md -o eval/questions.jsonl

Each line: {"q": ..., "file": ..., "page": int|null, "section": str|null, "type": "in"}.
The LLM is told to paraphrase (not copy) so keyword search can't win just by string matching.
A fixed list of off-topic questions (type "out") is appended to measure the refusal gate.
Review the file by hand before trusting the numbers: drop vague or wrong questions.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.providers import ProviderError, complete, resolve  # noqa: E402
from app.services.parsing import extract_segments, file_kind  # noqa: E402

PROMPT = (
    "Write ONE question that a student could ask and that is answered by a specific fact in the passage below "
    "(a name, date, law, number, definition or reason). The question must make sense on its own to someone "
    "who has not seen the passage: never refer to 'the statements', 'the options', 'the passage', 'the list', "
    "'the explanation', question numbers or ids. Use your own words: do not copy phrases longer than three words. "
    "Reply with the question only."
)
OUT_OF_SCOPE = [
    "Who won the 2022 FIFA World Cup?", "How do I bake a chocolate cake?", "What is the capital of France?",
    "Explain quantum entanglement in simple terms.", "What is your refund policy?", "What's the weather like today?",
    "Write a Python function that sorts a list.", "What is photosynthesis?", "Who painted the Mona Lisa?",
    "How many moons does Jupiter have?", "Recommend a good laptop for gaming.", "What is the boiling point of water?",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-o", "--out", default="eval/questions.jsonl")
    ap.add_argument("--min-chars", type=int, default=400, help="skip pages/sections shorter than this")
    ap.add_argument("--provider", default="gemini", help="LLM used to write questions (keeps the chat provider's quota free)")
    args = ap.parse_args()
    spec, model = resolve(args.provider, None)

    def ask(text: str) -> str:
        for attempt in range(6):
            try:
                return complete(spec, model, [{"role": "system", "content": PROMPT},
                                              {"role": "user", "content": text[:3000]}], max_tokens=400)
            except ProviderError as e:  # free tiers rate-limit: back off and retry
                if "429" not in str(e) and "503" not in str(e):
                    raise
                time.sleep(10 * (attempt + 1))
        raise SystemExit("gave up after repeated rate limits")

    rows = []
    for f in args.files:
        path = Path(f)
        segs, _ = extract_segments(path.read_bytes(), file_kind(path.name) or "text")
        for seg in segs:
            if len(seg.text) < args.min_chars:
                continue
            q = ask(seg.text).strip().strip('"')
            if q:
                rows.append({"q": q, "file": path.name, "page": seg.page, "section": seg.section, "type": "in"})
                print(f"{path.name} p.{seg.page} {seg.section or ''}: {q}")
    rows += [{"q": q, "file": None, "page": None, "section": None, "type": "out"} for q in OUT_OF_SCOPE]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} questions to {args.out}")


if __name__ == "__main__":
    main()
