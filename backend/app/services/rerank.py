"""Cross-encoder re-ranking: scores how well each retrieved chunk answers the question.

The score does two jobs:
1. ordering: the fused vector+keyword candidates are re-sorted by real relevance;
2. grounding gate: chunks below RERANK_MIN_SCORE are dropped, and if none survive the bot
   refuses without calling the LLM, so it never "answers" from the model's general knowledge.

Calibrated on the nextias test docs (ms-marco-MiniLM-L-6-v2): answerable questions scored
+2.6 to +9.8, off-topic ones -7.9 to -11.3; the default threshold (-2.0) sits in that gap.
"""
import os
from functools import lru_cache
from typing import Protocol

from ..config import get_settings


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model: str, cache_dir: str | None, max_chars: int):
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from fastembed.rerank.cross_encoder import TextCrossEncoder  # lazy: heavy import

        self.model = TextCrossEncoder(model, cache_dir=cache_dir)
        self.max_chars = max_chars  # the model reads 512 tokens at most; shorter is much faster on CPU

    def score(self, query, texts):
        return [float(s) for s in self.model.rerank(query, [t[:self.max_chars] for t in texts], batch_size=32)]


@lru_cache
def get_reranker() -> Reranker | None:
    """None = re-ranking (and the grounding gate) switched off: RERANKER=none."""
    s = get_settings()
    if s.reranker == "none":
        return None
    return CrossEncoderReranker(s.reranker_model, s.embedding_cache_dir, s.rerank_max_chars)
