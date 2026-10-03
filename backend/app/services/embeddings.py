"""Embedding providers.

- fastembed: local ONNX model (BAAI/bge-small-en-v1.5, 384-d). No API key; ~130MB download on first use.
- openai:    text-embedding-3-small truncated to EMBEDDING_DIM dimensions.
- hash:      deterministic bag-of-words hashing; offline, used by tests.
"""
import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from ..config import get_settings


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


class FastEmbedder:
    def __init__(self, model: str, dim: int, cache_dir: str | None = None):
        import os

        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from fastembed import TextEmbedding  # lazy: heavy import

        self.model = TextEmbedding(model_name=model, cache_dir=cache_dir)
        self.dim = dim

    def embed_documents(self, texts):
        return [v.tolist() for v in self.model.embed(texts, batch_size=32)]

    def embed_query(self, text):
        return next(iter(self.model.query_embed(text))).tolist()


class OpenAIEmbedder:
    def __init__(self, api_key: str, dim: int):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.dim = dim

    def embed_documents(self, texts):
        out = []
        for i in range(0, len(texts), 96):
            r = self.client.embeddings.create(
                model="text-embedding-3-small", input=texts[i:i + 96], dimensions=self.dim)
            out += [d.embedding for d in r.data]
        return out

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "hash":
        return HashEmbedder(s.embedding_dim)
    if s.embedding_provider == "openai":
        return OpenAIEmbedder(s.openai_api_key, s.embedding_dim)
    return FastEmbedder(s.embedding_model, s.embedding_dim, s.embedding_cache_dir)
