"""The grounding gate: answers come only from documents; off-topic questions are refused
without calling the LLM. Uses a fake cross-encoder so tests stay offline and fast."""
import re

import pytest

import app.services.chat as chat_service
import app.services.retrieval as retrieval
from app.services.chat import NOT_FOUND
from conftest import signup, sse_events
from test_bots_and_chat import make_bot_with_doc


class KeywordReranker:
    """Scores a chunk +5 per shared content word with the query, -10 when nothing is shared."""
    def score(self, query, texts):
        q = {w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 3}
        return [5.0 * len(q & set(re.findall(r"[a-z]+", t.lower()))) or -10.0 for t in texts]


@pytest.fixture
def gate(monkeypatch):
    monkeypatch.setattr(retrieval, "get_reranker", lambda: KeywordReranker())


def ask(client, bot, message, cid=None):
    body = {"message": message, **({"conversation_id": cid} if cid else {})}
    ev = sse_events(client.post(f"/api/bots/{bot['id']}/chat", json=body).text)
    return ev, "".join(e.get("text", "") for e in ev if e["type"] == "token")


def test_off_topic_question_is_refused_without_calling_the_llm(client, gate, monkeypatch):
    signup(client)
    bot = make_bot_with_doc(client)
    monkeypatch.setattr(chat_service, "stream_chat", lambda *a, **k: pytest.fail("LLM must not be called"))
    ev, answer = ask(client, bot, "who won the football world cup?")
    assert answer == NOT_FOUND
    assert next(e for e in ev if e["type"] == "sources")["items"] == []
    done = ev[-1]
    assert done["type"] == "done" and done["grounded"] is False and done["provider"] is None
    convs = client.get(f"/api/bots/{bot['id']}/conversations").json()
    msgs = client.get(f"/api/bots/{bot['id']}/conversations/{convs[0]['id']}").json()["messages"]
    assert [m["content"] for m in msgs] == ["who won the football world cup?", NOT_FOUND]


def test_on_topic_question_uses_only_relevant_chunks(client, gate):
    signup(client)
    bot = make_bot_with_doc(client)
    ev, answer = ask(client, bot, "how long does express shipping take?")
    sources = next(e for e in ev if e["type"] == "sources")["items"]
    assert sources and all(s["score"] >= -2.0 for s in sources)
    assert ev[-1]["grounded"] is True and "Express" in answer


def test_follow_up_retries_retrieval_with_the_previous_question(client, gate):
    signup(client)
    bot = make_bot_with_doc(client)
    ev, _ = ask(client, bot, "how long does express shipping take?")
    ev2, answer = ask(client, bot, "and why?", cid=ev[0]["conversation_id"])  # matches nothing on its own
    assert answer != NOT_FOUND and next(e for e in ev2 if e["type"] == "sources")["items"]


def test_api_docs_are_off_by_default(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_small_talk_gets_the_greeting_without_llm(client, gate, monkeypatch):
    signup(client)
    bot = make_bot_with_doc(client)
    monkeypatch.setattr(chat_service, "stream_chat", lambda *a, **k: pytest.fail("LLM must not be called"))
    ev, answer = ask(client, bot, "hi!")
    assert answer == bot["greeting"] and ev[-1]["grounded"] is False
    assert sum(e["type"] == "sources" for e in ev) == 1


def test_answer_tidying_drops_bold_and_out_of_range_citations():
    from app.services.chat import tidy_answer
    parts = ["The **Competition", " Act*", "* replaced it [1][9] and [2]."]
    assert "".join(tidy_answer(iter(parts), 2)) == "The Competition Act replaced it [1] and [2]."


def test_what_can_you_do_describes_the_bot_without_llm(client, gate, monkeypatch):
    signup(client)
    bot = make_bot_with_doc(client)
    monkeypatch.setattr(chat_service, "stream_chat", lambda *a, **k: pytest.fail("LLM must not be called"))
    _, answer = ask(client, bot, "what does this bot can do?")
    assert bot["name"] in answer and "faq" in answer and "isn't covered" in answer
