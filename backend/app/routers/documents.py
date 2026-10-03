import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Bot, Document
from ..schemas import DocumentOut
from ..services.ingest import ingest_document
from ..services.parsing import file_kind
from .deps import owned_bot

router = APIRouter(prefix="/api/bots/{bot_id}/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    return db.scalars(select(Document).where(Document.bot_id == bot.id).order_by(Document.created_at.desc())).all()


@router.post("", response_model=DocumentOut, status_code=202)
async def upload_document(background: BackgroundTasks, file: UploadFile = File(...),
                          bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    kind = file_kind(file.filename or "")
    if not kind:
        raise HTTPException(415, "only .pdf, .txt and .md files are supported")
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"file is larger than {get_settings().max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "file is empty")
    safe_name = (file.filename or "upload").replace("\\", "/").split("/")[-1][:255]
    doc = Document(bot_id=bot.id, owner_id=bot.owner_id, filename=safe_name, size_bytes=len(data))
    db.add(doc)
    db.commit()
    background.add_task(ingest_document, doc.id, data, kind)
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.bot_id == bot.id))
    if not doc:
        raise HTTPException(404, "document not found")
    db.delete(doc)
    db.commit()
