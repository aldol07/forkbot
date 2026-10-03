from app.routers.public import host_allowed, origin_host
from conftest import signup, sse_events
from test_bots_and_chat import make_bot_with_doc

V = {"visitor_id": "visitor-aaaa1111"}


def test_host_matching():
    assert host_allowed("localhost", ["localhost"])
    assert host_allowed("shop.acme.io", ["*.acme.io"])
    assert not host_allowed("acme.io", ["*.acme.io"])
    assert not host_allowed("evilacme.io", ["*.acme.io"])
    assert not host_allowed("acme.io.evil.com", ["acme.io"])
    assert not host_allowed(None, ["localhost"])
    assert origin_host("http://localhost:5500") == "localhost"
    assert origin_host("null") is None and origin_host("javascript:alert(1)") is None


def test_widget_flow_and_allow_list(client):
    signup(client)
    bot = make_bot_with_doc(client)
    pid = bot["public_id"]
    client.cookies.clear()  # widget visitors are anonymous

    ok = {"Origin": "http://localhost:5173"}
    r = client.get(f"/public/bots/{pid}", headers=ok)
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "http://localhost:5173"

    pre = client.options(f"/public/bots/{pid}/chat", headers={**ok, "Access-Control-Request-Method": "POST"})
    assert pre.status_code == 204

    r = client.post(f"/public/bots/{pid}/chat", json={"message": "what is the refund window?", **V}, headers=ok)
    assert r.status_code == 200
    assert "30 days" in "".join(e.get("text", "") for e in sse_events(r.text))

    bad = {"Origin": "https://evil.example"}
    assert client.post(f"/public/bots/{pid}/chat", json={"message": "hi", **V}, headers=bad).status_code == 403
    assert "access-control-allow-origin" not in client.post(f"/public/bots/{pid}/chat", json={"message": "hi", **V}, headers=bad).headers
    assert client.options(f"/public/bots/{pid}/chat", headers=bad).status_code == 403
    assert client.post(f"/public/bots/{pid}/chat", json={"message": "hi", **V}).status_code == 403  # no Origin
    assert client.get("/public/bots/bot_doesnotexist", headers=ok).status_code == 404


def test_widget_cannot_override_provider(client):
    signup(client)
    bot = make_bot_with_doc(client)
    client.cookies.clear()
    r = client.post(f"/public/bots/{bot['public_id']}/chat",
                    json={"message": "refund?", "provider": "openai", **V}, headers={"Origin": "http://localhost"})
    assert sse_events(r.text)[-1]["provider"] == "mock"


def test_widget_js_served(client):
    r = client.get("/widget.js")
    assert r.status_code == 200 and "data-bot-id" in r.text


def test_same_origin_get_uses_referer(client):
    signup(client)
    bot = client.post("/api/bots", json={"name": "Ref"}).json()
    client.cookies.clear()
    r = client.get(f"/public/bots/{bot['public_id']}", headers={"Referer": "http://localhost:8000/demo?bot=x"})
    assert r.status_code == 200 and r.json()["name"] == "Ref"
    assert client.get(f"/public/bots/{bot['public_id']}", headers={"Referer": "https://evil.example/x"}).status_code == 403
