"""Document ingestion: parse → chunk → embed → store. Runs as a background task (Celery in phase 2)."""
import logging
import uuid

from sqlalchemy import delete

from ..config import get_settings
from ..db import SessionLocal
from ..models import Chunk, Document
from .chunking import chunk_text
from .embeddings import get_embedder
from .parsing import extract_text

log = logging.getLogger("botforge.ingest")


def ingest_document(document_id: uuid.UUID, data: bytes, kind: str) -> None:
    s = get_settings()
    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if not doc:
            return
        doc.status = "processing"
        db.commit()
        try:
            text = extract_text(data, kind)
            if not text:
                raise ValueError("no extractable text (scanned PDF? OCR comes in Parcha)")
            chunks = chunk_text(text, s.chunk_size, s.chunk_overlap)
            vectors = get_embedder().embed_documents(chunks)
            db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            db.add_all([
                Chunk(bot_id=doc.bot_id, owner_id=doc.owner_id, document_id=doc.id,
                      ord=i, content=c, embedding=v)
                for i, (c, v) in enumerate(zip(chunks, vectors))
            ])
            doc.n_chunks, doc.status, doc.error = len(chunks), "ready", None
            db.commit()
            log.info("ingested %s: %d chunks", doc.filename, len(chunks))
        except Exception as e:  # noqa: BLE001: surface any failure on the document row
            db.rollback()
            doc = db.get(Document, document_id)
            doc.status, doc.error = "failed", str(e)[:500]
            db.commit()
            log.exception("ingest failed for %s", document_id)
