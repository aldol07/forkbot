"""Document ingestion: (stored original) → parse into page/section segments → chunk → embed → store.

Runs as a background task (Celery in phase 2). Re-indexing calls this again without `data`,
which re-reads the original from object storage.
"""
import logging
import time
import uuid

from sqlalchemy import delete, insert

from ..config import get_settings
from ..db import SessionLocal
from ..models import Chunk, Document
from ..storage import get_storage
from .chunking import chunk_text
from .embeddings import get_embedder
from .parsing import extract_segments, file_kind

log = logging.getLogger("forkbot.ingest")


def ingest_document(document_id: uuid.UUID, data: bytes | None = None) -> None:
    s = get_settings()
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if not doc:
            return
        doc.status, doc.error = "processing", None
        db.commit()
        try:
            t0 = time.perf_counter()
            if data is None:
                if not doc.storage_key:
                    raise ValueError("original file was not stored; upload it again")
                data = get_storage().get(doc.storage_key)
            segments, n_pages = extract_segments(data, file_kind(doc.filename) or "text")
            t_parse = time.perf_counter()
            pieces = [(seg, c) for seg in segments for c in chunk_text(seg.text, s.chunk_size, s.chunk_overlap)]
            if not pieces:
                raise ValueError("no extractable text (scanned PDF? image/OCR support is coming next)")
            vectors = get_embedder().embed_documents([c for _, c in pieces])
            t_embed = time.perf_counter()
            db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            # Core bulk insert (batched multi-row INSERTs, no per-object ORM work or RETURNING):
            # a 484-page book is ~2k rows, which matters over the network to a hosted database.
            db.execute(insert(Chunk), [
                dict(bot_id=doc.bot_id, owner_id=doc.owner_id, document_id=doc.id, ord=i,
                     kind="text", page=seg.page, section=seg.section, content=c, embedding=v)
                for i, ((seg, c), v) in enumerate(zip(pieces, vectors))
            ])
            doc.n_chunks, doc.n_pages, doc.status = len(pieces), n_pages, "ready"
            db.commit()
            t_end = time.perf_counter()
            log.info("ingested %s: %d pages, %d chunks | parse %.1fs, embed %.1fs, store %.1fs",
                     doc.filename, n_pages, len(pieces), t_parse - t0, t_embed - t_parse, t_end - t_embed)
        except Exception as e:  # noqa: BLE001: surface any failure on the document row
            db.rollback()
            doc = db.get(Document, document_id)
            doc.status, doc.error = "failed", str(e)[:500]
            db.commit()
            log.exception("ingest failed for %s", document_id)
