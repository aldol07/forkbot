"""Extract text from uploaded files as segments that remember where they came from.

PDF  → one segment per page (page = 1-based page number)
MD   → one segment per heading section (section = "Heading › Subheading")
TXT  → one segment
Chunks never cross a segment, so every citation can point at an exact page or section.
"""
import io
import re
from dataclasses import dataclass

from pypdf import PdfReader

ALLOWED = {".pdf": "pdf", ".txt": "text", ".md": "markdown", ".markdown": "markdown"}
CONTENT_TYPES = {"pdf": "application/pdf", "text": "text/plain", "markdown": "text/markdown"}

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Segment:
    text: str
    page: int | None = None
    section: str | None = None


def file_ext(filename: str) -> str | None:
    name = filename.lower()
    for ext in ALLOWED:
        if name.endswith(ext):
            return ext
    return None


def file_kind(filename: str) -> str | None:
    ext = file_ext(filename)
    return ALLOWED[ext] if ext else None


def normalise(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_segments(data: bytes, kind: str) -> tuple[list[Segment], int]:
    """Returns (segments, n_pages). n_pages is 0 for non-PDF files."""
    if kind == "pdf":
        if not data.startswith(b"%PDF"):
            raise ValueError("file is not a valid PDF")
        reader = PdfReader(io.BytesIO(data))
        segs = [Segment(normalise(p.extract_text() or ""), page=i)
                for i, p in enumerate(reader.pages, start=1)]
        return [s for s in segs if s.text], len(reader.pages)
    text = data.decode("utf-8", errors="replace")
    if kind == "markdown":
        return _markdown_sections(text), 0
    text = normalise(text)
    return ([Segment(text)] if text else []), 0


def _markdown_sections(text: str) -> list[Segment]:
    segs: list[Segment] = []
    path: list[tuple[int, str]] = []  # (level, title) of the current heading chain
    buf: list[str] = []
    in_fence = False

    def flush():
        body = normalise("\n".join(buf))
        if body:
            label = " › ".join(t for _, t in path)[:300] or None
            segs.append(Segment(body, section=label))
        buf.clear()

    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush()
            level, title = len(m.group(1)), m.group(2).strip()
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, title))
        buf.append(line)  # keep the heading line in the text so it's searchable
    flush()
    return segs
