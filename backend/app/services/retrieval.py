"""Hybrid retrieval: pgvector cosine + Postgres full-text → Reciprocal Rank Fusion → grounding gate.

The gate is the cross-encoder threshold when a re-ranker is configured, otherwise the similarity
gate: the closest chunk must reach SIMILARITY_MIN cosine similarity (see services/rerank.py)."""
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Chunk, Document
from .embeddings import Embedder, get_embedder
from .rerank import get_reranker

RRF_K = 60


@dataclass
class Hit:
    chunk_id: int
    content: str
    filename: str
    score: float
    vector_rank: int | None
    keyword_rank: int | None
    page: int | None = None
    section: str | None = None
    kind: str = "text"
    rerank_score: float | None = None

    @property
    def label(self) -> str:
        """Citation label, e.g. "faq.pdf · p.3" or "guide.md · Setup › Install"."""
        parts = [self.filename]
        if self.page:
            parts.append(f"p.{self.page}")
        if self.section:
            parts.append(self.section)
        return " · ".join(parts)


def vector_search(db: Session, bot_id: uuid.UUID, qvec: list[float], k: int) -> list[tuple[int, float]]:
    """(chunk id, cosine similarity), closest first."""
    dist = Chunk.embedding.cosine_distance(qvec)
    q = select(Chunk.id, dist).where(Chunk.bot_id == bot_id).order_by(dist).limit(k)
    return [(cid, 1.0 - d) for cid, d in db.execute(q)]


# Chunks matching ANY query term, scored by the summed IDF (rarity within this bot) of the terms they
# contain, ts_rank_cd as tie-break. Requiring every word (websearch_to_tsquery) misses "answer to
# question 01PRE-Q01" when the chunk lacks the word "question"; plain OR + ts_rank_cd lets the 227
# chunks saying "question" bury the single chunk holding the id. IDF makes the rare term win.
# Lexemes come from to_tsvector, so they're already stemmed: the 'simple' config won't re-stem them.
_KEYWORD_SQL = text("""
WITH terms AS (
    SELECT lex, (SELECT count(*) FROM chunks c
                 WHERE c.bot_id = :bot AND c.tsv @@ quote_literal(lex)::tsquery) AS df
    FROM unnest(tsvector_to_array(to_tsvector('english', :query))) AS lex
), weighted AS (
    SELECT lex, quote_literal(lex)::tsquery AS tq,
           ln(((SELECT count(*) FROM chunks WHERE bot_id = :bot) + 1.0) / df) AS idf
    FROM terms WHERE df > 0
), anyterm AS (
    SELECT to_tsquery('simple', string_agg(quote_literal(lex), ' | ')) AS q FROM weighted
)
SELECT c.id FROM chunks c, anyterm
WHERE c.bot_id = :bot AND c.tsv @@ anyterm.q
ORDER BY (SELECT sum(w.idf) FROM weighted w WHERE c.tsv @@ w.tq) DESC,
         ts_rank_cd(c.tsv, anyterm.q) DESC
LIMIT :k
""")


def keyword_search(db: Session, bot_id: uuid.UUID, query: str, k: int) -> list[int]:
    return list(db.scalars(_KEYWORD_SQL, {"bot": bot_id, "query": query, "k": k}))


def rrf(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return scores


def retrieve(db: Session, bot_id: uuid.UUID, query: str, k: int = 6, mode: str = "hybrid",
             rerank: bool = True, embedder: Embedder | None = None) -> list[Hit]:
    """Up to k chunks for the query, best first. An empty list means "the documents don't cover this".

    rerank=True applies the grounding gate: the cross-encoder threshold if a re-ranker is configured,
    else the similarity gate. mode: hybrid | vector | keyword (the latter two exist for the eval).
    """
    s = get_settings()
    reranker = get_reranker() if rerank else None
    pool = max(k * 3, 20)
    qvec = (embedder or get_embedder()).embed_query(query) if mode != "keyword" else None
    vec_hits = vector_search(db, bot_id, qvec, pool) if qvec is not None else []
    vec = [cid for cid, _ in vec_hits]
    if rerank and not reranker and vec_hits and vec_hits[0][1] < s.similarity_min:
        return []  # similarity gate: even the closest chunk isn't about this question
    kw = keyword_search(db, bot_id, query, pool) if mode != "vector" else []
    scores = rrf([r for r in (vec, kw) if r])
    n = max(k, s.rerank_candidates) if reranker else k
    top = sorted(scores, key=scores.get, reverse=True)[:n]
    if reranker:
        # RRF favours chunks found by both searches; make sure each search's best few still reach
        # the cross-encoder (an exact id like "01PRE-Q01" is often found by keywords alone).
        top += [c for c in kw[:3] + vec[:3] if c not in top]
    if not top:
        return []
    rows = db.execute(
        select(Chunk.id, Chunk.content, Chunk.page, Chunk.section, Chunk.kind, Document.filename)
        .join(Document, Document.id == Chunk.document_id).where(Chunk.id.in_(top))
    ).all()
    by_id = {r.id: r for r in rows}
    vpos = {c: i + 1 for i, c in enumerate(vec)}
    kpos = {c: i + 1 for i, c in enumerate(kw)}
    hits = [Hit(c, by_id[c].content, by_id[c].filename, scores[c], vpos.get(c), kpos.get(c),
                by_id[c].page, by_id[c].section, by_id[c].kind)
            for c in top if c in by_id]
    if not reranker:
        return hits[:k]
    for h, sc in zip(hits, reranker.score(query, [h.content for h in hits])):
        h.rerank_score = sc
    hits = [h for h in hits if h.rerank_score >= s.rerank_min_score]
    return sorted(hits, key=lambda h: h.rerank_score, reverse=True)[:k]
