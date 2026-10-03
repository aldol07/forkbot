"""Hybrid retrieval: pgvector cosine + Postgres full-text, fused with Reciprocal Rank Fusion."""
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Chunk, Document
from .embeddings import get_embedder

RRF_K = 60


@dataclass
class Hit:
    chunk_id: int
    content: str
    filename: str
    score: float
    vector_rank: int | None
    keyword_rank: int | None


def vector_search(db: Session, bot_id: uuid.UUID, qvec: list[float], k: int) -> list[int]:
    q = (select(Chunk.id).where(Chunk.bot_id == bot_id)
         .order_by(Chunk.embedding.cosine_distance(qvec)).limit(k))
    return list(db.scalars(q))


def keyword_search(db: Session, bot_id: uuid.UUID, query: str, k: int) -> list[int]:
    tsq = func.websearch_to_tsquery("english", query)
    q = (select(Chunk.id).where(Chunk.bot_id == bot_id, Chunk.tsv.op("@@")(tsq))
         .order_by(func.ts_rank_cd(Chunk.tsv, tsq).desc()).limit(k))
    return list(db.scalars(q))


def rrf(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return scores


def retrieve(db: Session, bot_id: uuid.UUID, query: str, k: int = 6, mode: str = "hybrid") -> list[Hit]:
    """mode: hybrid | vector | keyword (the latter two exist for the phase-2 eval)."""
    pool = max(k * 3, 20)
    vec = vector_search(db, bot_id, get_embedder().embed_query(query), pool) if mode != "keyword" else []
    kw = keyword_search(db, bot_id, query, pool) if mode != "vector" else []
    scores = rrf([r for r in (vec, kw) if r])
    top = sorted(scores, key=scores.get, reverse=True)[:k]
    if not top:
        return []
    rows = db.execute(
        select(Chunk.id, Chunk.content, Document.filename)
        .join(Document, Document.id == Chunk.document_id).where(Chunk.id.in_(top))
    ).all()
    by_id = {r.id: r for r in rows}
    vpos = {c: i + 1 for i, c in enumerate(vec)}
    kpos = {c: i + 1 for i, c in enumerate(kw)}
    return [Hit(c, by_id[c].content, by_id[c].filename, scores[c], vpos.get(c), kpos.get(c))
            for c in top if c in by_id]
