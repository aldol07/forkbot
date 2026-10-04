"""Optional cross-encoder re-ranking.

When a re-ranker is configured, its score does two jobs:
1. ordering: the fused vector+keyword candidates are re-sorted by real relevance;
2. grounding gate: chunks below RERANK_MIN_SCORE are dropped, and if none survive the bot refuses
   without calling the LLM.

Without one (the default, RERANKER=none) retrieval uses the similarity gate instead: the closest
chunk's cosine similarity must reach SIMILARITY_MIN (see services/retrieval.py).

Calibration of the local cross-encoder (ms-marco-MiniLM-L-6-v2) on 60 answerable + 12 off-topic
questions: highest off-topic score -8.3; at -6.0 every off-topic question was refused and 5% of
answerable ones were. It is off because it needs ~160 MB of RAM and real CPU: on a 0.1-CPU free
host one question would take many seconds.
"""
from typing import Protocol


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...


# Local cross-encoder (fastembed). To use it again: uncomment this class and the branch in
# get_reranker(), add fastembed==0.7.1 back to requirements.txt and set RERANKER=cross-encoder.
#
# import os
#
# class CrossEncoderReranker:
#     def __init__(self, model: str, cache_dir: str | None, max_chars: int):
#         os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
#         from fastembed.rerank.cross_encoder import TextCrossEncoder  # lazy: heavy import
#
#         self.model = TextCrossEncoder(model, cache_dir=cache_dir)
#         self.max_chars = max_chars  # the model reads 512 tokens at most; shorter is much faster on CPU
#
#     def score(self, query, texts):
#         return [float(s) for s in self.model.rerank(query, [t[:self.max_chars] for t in texts], batch_size=32)]


def get_reranker() -> Reranker | None:
    """None = no re-ranker; retrieval falls back to the similarity gate."""
    # from functools import lru_cache  (decorate this function with @lru_cache when re-enabling)
    # from ..config import get_settings
    # s = get_settings()
    # if s.reranker == "cross-encoder":
    #     return CrossEncoderReranker(s.reranker_model, s.embedding_cache_dir, s.rerank_max_chars)
    return None
