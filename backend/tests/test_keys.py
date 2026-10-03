"""Bring your own key: users paste provider keys; bots use them; the server's keys can be switched off."""
import pytest
from sqlalchemy import select

import app.routers.keys as keys_router
import app.services.chat as chat_service
from app.config import get_settings
from app.db import SessionLocal
from app.models import ProviderKey
from conftest import signup, sse_events
from test_bots_and_chat import make_bot_with_doc

GOOD, BAD = "gsk_test_good_key_1234", "gsk_test_bad_key_9999"


@pytest.fixture(autouse=True)
def fake_check(monkeypatch):
    monkeypatch.setattr(keys_router, "check_key", lambda provider, key: (key == GOOD, "ok" if key == GOOD else "rejected"))


@pytest.fixture
def no_server_keys():
    s = get_settings()
    old = (s.server_llm_keys, s.groq_api_key)
    s.server_llm_keys, s.groq_api_key = False, "server-key-must-not-be-used"
    yield
    s.server_llm_keys, s.groq_api_key = old


def test_save_list_test_delete_never_returns_the_key(client):
    signup(client)
    assert client.put("/api/keys/groq", json={"api_key": BAD}).status_code == 400  # rejected keys aren't stored
    r = client.put("/api/keys/groq", json={"api_key": GOOD})
    assert r.status_code == 200 and r.json()["last4"] == "1234"
    listing = {k["provider"]: k for k in client.get("/api/keys").json()}
    assert listing["groq"]["saved"] and listing["groq"]["last4"] == "1234" and not listing["openai"]["saved"]
    assert GOOD not in client.get("/api/keys").text
    assert client.post("/api/keys/groq/test", json={}).json()["ok"] is True          # the saved key
    assert client.post("/api/keys/openai/test", json={"api_key": BAD}).json()["ok"] is False  # a pasted one
    assert client.post("/api/keys/openai/test", json={}).status_code == 404
    assert client.put("/api/keys/anthropic", json={"api_key": GOOD}).status_code == 422
    assert client.delete("/api/keys/groq").status_code == 204
    assert not {k["provider"]: k for k in client.get("/api/keys").json()}["groq"]["saved"]


def test_keys_are_encrypted_at_rest_and_private_to_the_account(client):
    signup(client)
    client.put("/api/keys/groq", json={"api_key": GOOD})
    with SessionLocal() as db:
        row = db.scalar(select(ProviderKey))
        assert GOOD not in row.key_encrypted and row.last4 == "1234"
    client.cookies.clear()
    signup(client, "b@example.com")
    assert not {k["provider"]: k for k in client.get("/api/keys").json()}["groq"]["saved"]


def test_bots_answer_with_the_owners_key(client, monkeypatch, no_server_keys):
    used = []

    def fake_stream(spec, model, messages):
        used.append((spec.name, spec.api_key))
        yield "Express takes 2 days [1]."

    monkeypatch.setattr(chat_service, "stream_chat", fake_stream)
    signup(client)
    bot = make_bot_with_doc(client)
    client.patch(f"/api/bots/{bot['id']}", json={"llm_provider": "groq"})

    ev = sse_events(client.post(f"/api/bots/{bot['id']}/chat", json={"message": "express shipping?"}).text)
    assert ev[-1]["type"] == "error" and "add your own" in ev[-1]["message"]  # server key not spent
    assert used == []

    client.put("/api/keys/groq", json={"api_key": GOOD})
    ev = sse_events(client.post(f"/api/bots/{bot['id']}/chat", json={"message": "express shipping?"}).text)
    assert ev[-1]["type"] == "done" and used == [("groq", GOOD)]
    providers = {p["name"]: p for p in client.get("/api/providers").json()}
    assert providers["groq"]["key_source"] == "user" and "ollama" not in providers
