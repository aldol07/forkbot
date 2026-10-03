"""Extract plain text from uploaded files."""
import io
import re

from pypdf import PdfReader

ALLOWED = {".pdf": "pdf", ".txt": "text", ".md": "text", ".markdown": "text"}


def file_kind(filename: str) -> str | None:
    name = filename.lower()
    for ext, kind in ALLOWED.items():
        if name.endswith(ext):
            return kind
    return None


def extract_text(data: bytes, kind: str) -> str:
    if kind == "pdf":
        if not data.startswith(b"%PDF"):
            raise ValueError("file is not a valid PDF")
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
        text = "\n\n".join(pages)
    else:
        text = data.decode("utf-8", errors="replace")
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
