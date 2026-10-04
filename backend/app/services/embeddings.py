"""Embedding providers.

- gemini: gemini-embedding-001 through Google's OpenAI-compatible endpoint (default; free tier).
- openai: text-embedding-3-small.
- hash:   deterministic bag-of-words hashing; offline, used by the tests.

Vectors are EMBEDDING_DIM (384) wide to match the `chunks.embedding` column. A bot owner's own
pasted key for the embedding provider is used when they have one (see embedder_for); otherwise the
server's key (EMBEDDING_API_KEY, else that provider's server key). Gemini's free tier allows 1,000
embedding requests per day per key, and every question costs one, so owners' keys spread the load.

On the eval set gemini-embedding-001 @384 found the right page as often as the local model it
replaced (95.0% in the top 6) while separating off-topic questions better. Switching provider puts
vectors in a different space: re-index existing documents afterwards.
"""
import hashlib
import logging
import math
import re
import time
from functools import lru_cache
from typing import Protocol

from ..config import get_settings

log = logging.getLogger("forkbot.embeddings")


class Embedder(Protocol):
    dim: int
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Feature-hashed unigrams + bigrams, L2-normalised. Good enough for tests and demos."""

    def __init__(self, dim: int):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        toks = re.findall(r"\w+", text.lower())
        feats = toks + [a + "_" + b for a, b in zip(toks, toks[1:])]
        v = [0.0] * self.dim
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "little")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class EmbeddingQuotaError(RuntimeError):
    """The provider's quota is used up for hours (e.g. Gemini free tier: 1,000 requests/day)."""


def _retry_after_seconds(message: str) -> float | None:
    m = re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", message)
    if not m:
        return None
    h, mins, sec = m.groups()
    return int(h or 0) * 3600 + int(mins or 0) * 60 + float(sec)


class APIEmbedder:
    """Any OpenAI-compatible /embeddings endpoint. Batches, and backs off on free-tier rate limits
    (ingesting a long book can take a few minutes on Gemini's free tier)."""

    BATCH = 50

    def __init__(self, api_key: str, model: str, dim: int, base_url: str | None = None):
        from openai import OpenAI

        if not api_key:
            raise RuntimeError("no embedding API key: set EMBEDDING_API_KEY (or the provider's API key) in .env")
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=60, max_retries=0)
        self.model, self.dim = model, dim

    def _create(self, texts: list[str]) -> list[list[float]]:
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

        for attempt in range(8):
            try:
                r = self.client.embeddings.create(model=self.model, input=texts, dimensions=self.dim)
                return [d.embedding for d in r.data]
            except (RateLimitError, InternalServerError, APIConnectionError, APITimeoutError) as e:
                retry_after = _retry_after_seconds(str(e))
                if isinstance(e, RateLimitError) and retry_after and retry_after > 120:
                    hours = retry_after / 3600
                    when = f"about {hours:.0f} h" if hours >= 1 else f"about {retry_after / 60:.0f} min"
                    raise EmbeddingQuotaError(f"the embedding quota is used up (resets in {when})") from e
                wait = min(10 * 2 ** attempt, 120)
                log.warning("embedding call failed (%s), retrying in %ss", type(e).__name__, wait)
                time.sleep(wait)
        raise RuntimeError("embedding provider kept failing; try again later")

    def embed_documents(self, texts):
        out = []
        for i in range(0, len(texts), self.BATCH):
            out += self._create(texts[i:i + self.BATCH])
        return out

    def embed_query(self, text):
        return self._create([text])[0]


# Local embeddings (fastembed, BAAI/bge-small-en-v1.5, 384-d, ONNX on CPU). Turned off because the
# model needs ~170 MB of RAM (and ~830 MB peak while indexing), more than small free hosts give.
# To use it again: uncomment this class and the "fastembed" branch in get_embedder(), add
# fastembed==0.7.1 back to requirements.txt, set EMBEDDING_PROVIDER=fastembed and re-index documents.
#
# class FastEmbedder:
#     def __init__(self, model: str, dim: int, cache_dir: str | None = None):
#         import os
#
#         os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
#         from fastembed import TextEmbedding  # lazy: heavy import
#
#         self.model = TextEmbedding(model_name=model, cache_dir=cache_dir)
#         self.dim = dim
#
#     def embed_documents(self, texts):
#         return [v.tolist() for v in self.model.embed(texts, batch_size=32)]
#
#     def embed_query(self, text):
#         return next(iter(self.model.query_embed(text))).tolist()


def embedder_for(user_keys: dict[str, str] | None) -> Embedder:
    """The embedder a bot's owner should use: their own key for the embedding provider if saved."""
    own = (user_keys or {}).get(get_settings().embedding_provider)
    return get_embedder(own or "")


@lru_cache(maxsize=64)
def get_embedder(api_key: str = "") -> Embedder:
    """api_key overrides the server key (a bot owner's own key); empty = server key."""
    s = get_settings()
    if s.embedding_provider == "hash":
        return HashEmbedder(s.embedding_dim)
    if s.embedding_provider == "openai":
        return APIEmbedder(api_key or s.embedding_api_key or s.openai_api_key, s.embedding_model or "text-embedding-3-small",
                           s.embedding_dim)
    # if s.embedding_provider == "fastembed":
    #     return FastEmbedder(s.embedding_model, s.embedding_dim, s.embedding_cache_dir)
    if s.embedding_provider == "gemini":
        return APIEmbedder(api_key or s.embedding_api_key or s.gemini_api_key, s.embedding_model or "gemini-embedding-001",
                           s.embedding_dim, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    raise RuntimeError(f"unknown EMBEDDING_PROVIDER '{s.embedding_provider}' (gemini | openai | hash)")
