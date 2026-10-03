"""Recursive character chunking: paragraphs → sentences → words, with overlap."""
import re

_SEPARATORS = ["\n\n", "\n", r"(?<=[.!?])\s+", " "]


def _split(text: str, size: int, seps: list[str]) -> list[str]:
    if len(text) <= size:
        return [text]
    if not seps:
        return [text[i:i + size] for i in range(0, len(text), size)]
    sep, rest = seps[0], seps[1:]
    parts = re.split(sep, text) if sep.startswith("(") else text.split(sep)
    joiner = " " if sep.startswith("(") else sep
    out, buf = [], ""
    for p in parts:
        if not p.strip():
            continue
        if len(p) > size:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(_split(p, size, rest))
        elif len(buf) + len(joiner) + len(p) <= size:
            buf = f"{buf}{joiner}{p}" if buf else p
        else:
            out.append(buf)
            buf = p
    if buf:
        out.append(buf)
    return out


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    pieces = [p.strip() for p in _split(text, size, _SEPARATORS) if p.strip()]
    if overlap <= 0 or len(pieces) < 2:
        return pieces
    out = [pieces[0]]
    for prev, cur in zip(pieces, pieces[1:]):
        tail = prev[-overlap:]
        cut = tail.find(" ")
        tail = tail[cut + 1:] if cut != -1 else tail
        out.append(f"{tail} {cur}".strip())
    return out
