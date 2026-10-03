import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.config import get_settings
from app.db import SessionLocal
from app.models import Conversation, Document
from app.services.chat import purge_old_conversations
from app.services.parsing import extract_segments
from conftest import signup, sse_events
from test_bots_and_chat import DOC, make_bot_with_doc

V1, V2 = "visitor-aaaa1111", "visitor-bbbb2222"
WIDGET = {"Origin": "http://localhost:5173"}


def make_pdf(pages: list[str]) -> bytes:
    """Minimal valid PDF with one line of Helvetica text per page (no external deps)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode()}\nendstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {len(objs)} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def wait_ready(client, bot_id, doc_id=None):
    for _ in range(100):
        docs = client.get(f"/api/bots/{bot_id}/documents").json()
        d = next(x for x in docs if doc_id in (None, x["id"]))
        if d["status"] in ("ready", "failed"):
            return d
        time.sleep(0.05)
    raise AssertionError(f"document never finished: {d}")


def stored_files():
    root = get_settings().storage_dir
    return [os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs]


# ---------- parsing ----------

def test_pdf_segments_keep_page_numbers():
    segs, n_pages = extract_segments(make_pdf(["Refunds take 30 days.", "Shipping takes 5 days."]), "pdf")
    assert n_pages == 2
    assert [(s.page, s.text) for s in segs] == [(1, "Refunds take 30 days."), (2, "Shipping takes 5 days.")]


def test_markdown_sections_follow_headings_and_skip_code_fences():
    md = ("intro line\n# Setup\ntext a\n## Install\ntext b\n```\n# not a heading\n```\n"
          "## Configure\ntext c\n# Usage\ntext d\n").encode()
    segs, _ = extract_segments(md, "markdown")
    assert [s.section for s in segs] == [None, "Setup", "Setup › Install", "Setup › Configure", "Usage"]
    assert "# not a heading" in segs[2].text


# ---------- file storage ----------

def test_upload_keeps_original_download_and_dedupe(client):
    signup(client)
    bot = client.post("/api/bots", json={"name": "Files"}).json()
    r = client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("faq.txt", DOC, "text/plain")})
    assert r.status_code == 202 and r.json()["has_file"]
    doc = wait_ready(client, bot["id"])
    assert doc["status"] == "ready" and doc["content_type"] == "text/plain"

    dl = client.get(f"/api/bots/{bot['id']}/documents/{doc['id']}/file")
    assert dl.status_code == 200 and dl.content == DOC
    assert "faq.txt" in dl.headers["content-disposition"]

    dup = client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("copy.txt", DOC, "text/plain")})
    assert dup.status_code == 409 and "faq.txt" in dup.json()["detail"]


def test_reindex_rebuilds_from_stored_file(client):
    signup(client)
    bot = make_bot_with_doc(client)
    doc = client.get(f"/api/bots/{bot['id']}/documents").json()[0]
    r = client.post(f"/api/bots/{bot['id']}/documents/{doc['id']}/reindex")
    assert r.status_code == 202
    again = wait_ready(client, bot["id"], doc["id"])
    assert again["status"] == "ready" and again["n_chunks"] == doc["n_chunks"]

    # documents uploaded before file storage existed can't be re-indexed
    with SessionLocal() as db:
        db.execute(update(Document).where(Document.id == doc["id"]).values(storage_key=None))
        db.commit()
    assert client.post(f"/api/bots/{bot['id']}/documents/{doc['id']}/reindex").status_code == 409
    assert client.get(f"/api/bots/{bot['id']}/documents/{doc['id']}/file").status_code == 404


def test_delete_document_and_bot_remove_stored_files(client):
    signup(client)
    bot = make_bot_with_doc(client)
    doc = client.get(f"/api/bots/{bot['id']}/documents").json()[0]
    mine = lambda: [f for f in stored_files() if bot["id"] in f]  # noqa: E731
    assert len(mine()) == 1
    assert client.delete(f"/api/bots/{bot['id']}/documents/{doc['id']}").status_code == 204
    assert mine() == []

    client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("again.txt", DOC, "text/plain")})
    wait_ready(client, bot["id"])
    assert len(mine()) == 1
    assert client.delete(f"/api/bots/{bot['id']}").status_code == 204
    assert mine() == []


def test_other_users_cannot_download(client):
    signup(client)
    bot = make_bot_with_doc(client)
    doc = client.get(f"/api/bots/{bot['id']}/documents").json()[0]
    client.cookies.clear()
    signup(client, "b@example.com")
    assert client.get(f"/api/bots/{bot['id']}/documents/{doc['id']}/file").status_code == 404


def test_per_bot_document_limit(client):
    s = get_settings()
    old, s.max_docs_per_bot = s.max_docs_per_bot, 1
    try:
        signup(client)
        bot = make_bot_with_doc(client)
        r = client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("two.txt", b"other text", "text/plain")})
        assert r.status_code == 409 and "limit" in r.json()["detail"]
    finally:
        s.max_docs_per_bot = old


def test_pdf_citations_carry_page_numbers(client):
    signup(client)
    bot = client.post("/api/bots", json={"name": "Pdf"}).json()
    pdf = make_pdf(["Our office is in Pune.", "Refunds are accepted within 30 days of purchase."])
    client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("policy.pdf", pdf, "application/pdf")})
    doc = wait_ready(client, bot["id"])
    assert doc["status"] == "ready" and doc["n_pages"] == 2
    ev = sse_events(client.post(f"/api/bots/{bot['id']}/chat", json={"message": "refunds accepted days"}).text)
    sources = next(e for e in ev if e["type"] == "sources")["items"]
    assert sources[0]["filename"] == "policy.pdf" and sources[0]["page"] == 2


# ---------- conversations ----------

def test_dashboard_conversation_is_persisted_and_continued(client):
    signup(client)
    bot = make_bot_with_doc(client)
    ev = sse_events(client.post(f"/api/bots/{bot['id']}/chat", json={"message": "refund window?"}).text)
    cid = ev[0]["conversation_id"]
    ev2 = sse_events(client.post(f"/api/bots/{bot['id']}/chat",
                                 json={"message": "and express shipping?", "conversation_id": cid}).text)
    assert ev2[0]["conversation_id"] == cid and ev2[-1]["type"] == "done"

    convs = client.get(f"/api/bots/{bot['id']}/conversations").json()
    assert len(convs) == 1 and convs[0]["n_messages"] == 4 and convs[0]["title"] == "refund window?"
    detail = client.get(f"/api/bots/{bot['id']}/conversations/{cid}").json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant", "user", "assistant"]
    last = detail["messages"][-1]
    assert last["provider"] == "mock" and last["total_ms"] is not None and last["sources"]

    client.cookies.clear()
    signup(client, "b@example.com")
    assert client.get(f"/api/bots/{bot['id']}/conversations/{cid}").status_code == 404


def test_widget_conversation_belongs_to_its_visitor(client):
    signup(client)
    bot = make_bot_with_doc(client)
    pid = bot["public_id"]
    owner_cookies = dict(client.cookies)
    client.cookies.clear()

    ev = sse_events(client.post(f"/public/bots/{pid}/chat", headers=WIDGET,
                                json={"message": "refund window?", "visitor_id": V1}).text)
    cid = ev[0]["conversation_id"]

    r = client.get(f"/public/bots/{pid}/conversations/{cid}", params={"visitor_id": V1}, headers=WIDGET)
    assert r.status_code == 200 and [m["role"] for m in r.json()["messages"]] == ["user", "assistant"]
    assert r.headers["access-control-allow-origin"] == WIDGET["Origin"]
    assert client.get(f"/public/bots/{pid}/conversations/{cid}", params={"visitor_id": V2},
                      headers=WIDGET).status_code == 404
    assert client.get(f"/public/bots/{pid}/conversations/{cid}", params={"visitor_id": V1},
                      headers={"Origin": "https://evil.example"}).status_code == 403

    # another visitor presenting a stolen conversation id gets a fresh conversation instead
    ev = sse_events(client.post(f"/public/bots/{pid}/chat", headers=WIDGET,
                                json={"message": "hi", "visitor_id": V2, "conversation_id": cid}).text)
    assert ev[0]["conversation_id"] != cid

    client.cookies.update(owner_cookies)
    sources = {c["source"] for c in client.get(f"/api/bots/{bot['id']}/conversations").json()}
    assert sources == {"widget"}
    assert len(client.get(f"/api/bots/{bot['id']}/conversations", params={"source": "widget"}).json()) == 2


def test_retention_purges_only_old_widget_conversations(client):
    signup(client)
    bot = make_bot_with_doc(client)
    client.post(f"/api/bots/{bot['id']}/chat", json={"message": "dashboard chat"})
    client.post(f"/public/bots/{bot['public_id']}/chat", headers=WIDGET,
                json={"message": "widget chat", "visitor_id": V1})
    old = datetime.now(timezone.utc) - timedelta(days=get_settings().chat_retention_days + 1)
    with SessionLocal() as db:
        db.execute(update(Conversation).values(last_message_at=old))
        db.commit()
    assert purge_old_conversations() == 1
    left = client.get(f"/api/bots/{bot['id']}/conversations").json()
    assert [c["source"] for c in left] == ["dashboard"]


def test_keyword_search_finds_ids_without_every_query_word(client):
    from app.services.retrieval import retrieve
    signup(client)
    bot = client.post("/api/bots", json={"name": "Ids"}).json()
    text = (b"Q1. (01PRE-Q01) Consider the statements about the Election Commission. Answer: A\n\n"
            b"Q2. (01PRE-Q02) Consider the statements about the Finance Commission. Answer: C")
    client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("qs.txt", text, "text/plain")})
    wait_ready(client, bot["id"])
    with SessionLocal() as db:
        hits = retrieve(db, bot["id"], "What is the answer to question 01PRE-Q02?", mode="keyword")
    assert hits and "01PRE-Q02" in hits[0].content
