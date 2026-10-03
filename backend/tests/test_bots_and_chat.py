import time

from conftest import signup, sse_events

DOC = b"""Acme Widgets refund policy.
Customers can request a full refund within 30 days of purchase by emailing support@acme.test.

Shipping information.
Standard shipping takes 5 to 7 business days. Express shipping takes 2 days and costs $15.

Warranty.
All widgets carry a two year warranty against manufacturing defects."""


def make_bot_with_doc(client):
    bot = client.post("/api/bots", json={"name": "Acme Helper"}).json()
    r = client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("faq.txt", DOC, "text/plain")})
    assert r.status_code == 202, r.text
    for _ in range(50):
        docs = client.get(f"/api/bots/{bot['id']}/documents").json()
        if docs[0]["status"] in ("ready", "failed"):
            break
        time.sleep(0.05)
    assert docs[0]["status"] == "ready", docs
    assert docs[0]["n_chunks"] >= 1
    return bot


def test_bot_crud_and_tenant_isolation(client):
    signup(client)
    bot = client.post("/api/bots", json={"name": "Mine"}).json()
    assert bot["allowed_domains"] == ["localhost"]
    r = client.patch(f"/api/bots/{bot['id']}", json={"allowed_domains": ["https://Shop.Example.com/path", "*.acme.io"], "llm_provider": "mock"})
    assert r.status_code == 200
    assert r.json()["allowed_domains"] == ["shop.example.com", "*.acme.io"]
    assert client.patch(f"/api/bots/{bot['id']}", json={"llm_provider": "nope"}).status_code == 422

    client.cookies.clear()
    signup(client, "b@example.com")
    assert client.get("/api/bots").json() == []
    assert client.get(f"/api/bots/{bot['id']}").status_code == 404
    assert client.post(f"/api/bots/{bot['id']}/chat", json={"message": "hi"}).status_code == 404


def test_upload_validation(client):
    signup(client)
    bot = client.post("/api/bots", json={"name": "x"}).json()
    assert client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("a.exe", b"MZ", "application/octet-stream")}).status_code == 415
    r = client.post(f"/api/bots/{bot['id']}/documents", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 202
    time.sleep(0.2)
    doc = client.get(f"/api/bots/{bot['id']}/documents").json()[0]
    assert doc["status"] == "failed" and "PDF" in doc["error"]


def test_chat_streams_grounded_answer(client):
    signup(client)
    bot = make_bot_with_doc(client)
    r = client.post(f"/api/bots/{bot['id']}/chat", json={"message": "How long does express shipping take?", "provider": "mock"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = sse_events(r.text)
    assert ev[0]["type"] == "sources" and ev[0]["items"]
    answer = "".join(e["text"] for e in ev if e["type"] == "token")
    assert "Express" in answer
    done = ev[-1]
    assert done["type"] == "done" and done["provider"] == "mock" and done["first_token_ms"] is not None


def test_unconfigured_provider_reports_error(client):
    signup(client)
    bot = client.post("/api/bots", json={"name": "x"}).json()
    ev = sse_events(client.post(f"/api/bots/{bot['id']}/chat", json={"message": "hi", "provider": "openai"}).text)
    assert ev[-1]["type"] == "error" and "OPENAI_API_KEY" in ev[-1]["message"]


def test_providers_listing(client):
    signup(client)
    names = {p["name"]: p for p in client.get("/api/providers").json()}
    assert set(names) == {"groq", "openai", "gemini", "ollama", "mock"}
    assert names["mock"]["configured"] and names["mock"]["is_default"]
