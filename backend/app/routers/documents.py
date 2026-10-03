import hashlib
import uuid
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Bot, Document
from ..schemas import DocumentOut
from ..services.ingest import ingest_document
from ..services.parsing import CONTENT_TYPES, file_ext, file_kind
from ..storage import document_prefix, get_storage
from .deps import owned_bot

router = APIRouter(prefix="/api/bots/{bot_id}/documents", tags=["documents"])


def _owned_document(document_id: uuid.UUID, bot: Bot, db: Session) -> Document:
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.bot_id == bot.id))
    if not doc:
        raise HTTPException(404, "document not found")
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    return db.scalars(select(Document).where(Document.bot_id == bot.id).order_by(Document.created_at.desc())).all()


@router.post("", response_model=DocumentOut, status_code=202)
async def upload_document(background: BackgroundTasks, file: UploadFile = File(...),
                          bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    s = get_settings()
    filename = (file.filename or "upload").replace("\\", "/").split("/")[-1][:255]
    ext, kind = file_ext(filename), file_kind(filename)
    if not kind:
        raise HTTPException(415, "only .pdf, .txt and .md files are supported")
    limit = s.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"file is larger than {s.max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "file is empty")

    n_docs = db.scalar(select(func.count(Document.id)).where(Document.bot_id == bot.id)) or 0
    if n_docs >= s.max_docs_per_bot:
        raise HTTPException(409, f"this bot already has {s.max_docs_per_bot} documents (the limit); delete one first")
    used = db.scalar(select(func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.owner_id == bot.owner_id))
    if used + len(data) > s.max_storage_mb_per_user * 1024 * 1024:
        raise HTTPException(413, f"storage limit reached ({s.max_storage_mb_per_user} MB per account)")
    sha = hashlib.sha256(data).hexdigest()
    dup = db.scalar(select(Document).where(Document.bot_id == bot.id, Document.sha256 == sha,
                                           Document.status != "failed"))
    if dup:
        raise HTTPException(409, f"this file is already uploaded as {dup.filename}")

    doc_id = uuid.uuid4()
    key = document_prefix(bot.owner_id, bot.id, doc_id) + "original" + ext
    get_storage().put(key, data, CONTENT_TYPES[kind])
    doc = Document(id=doc_id, bot_id=bot.id, owner_id=bot.owner_id, filename=filename,
                   content_type=CONTENT_TYPES[kind], size_bytes=len(data), sha256=sha, storage_key=key)
    db.add(doc)
    try:
        db.commit()
    except Exception:
        get_storage().delete_prefix(document_prefix(bot.owner_id, bot.id, doc_id))
        raise
    background.add_task(ingest_document, doc.id, data)
    return doc


@router.get("/{document_id}/file")
def download_document(document_id: uuid.UUID, bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    doc = _owned_document(document_id, bot, db)
    if not doc.storage_key:
        raise HTTPException(404, "the original file wasn't kept for this document (uploaded before file storage)")
    try:
        data = get_storage().get(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(404, "stored file is missing")
    return Response(data, media_type=doc.content_type or "application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.filename)}",
        "Cache-Control": "private, no-store",
    })


@router.post("/{document_id}/reindex", response_model=DocumentOut, status_code=202)
def reindex_document(document_id: uuid.UUID, background: BackgroundTasks,
                     bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    doc = _owned_document(document_id, bot, db)
    if not doc.storage_key:
        raise HTTPException(409, "the original file wasn't kept for this document; upload it again instead")
    if doc.status in ("pending", "processing"):
        raise HTTPException(409, "this document is already being processed")
    doc.status, doc.error = "pending", None
    db.commit()
    background.add_task(ingest_document, doc.id)
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    doc = _owned_document(document_id, bot, db)
    db.delete(doc)
    db.commit()
    get_storage().delete_prefix(document_prefix(bot.owner_id, bot.id, document_id))
