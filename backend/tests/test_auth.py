from conftest import signup


def test_signup_login_me_logout(client):
    signup(client)
    assert client.get("/api/auth/me").json()["email"] == "a@example.com"
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/login", json={"email": "A@example.com", "password": "password123"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_duplicate_and_bad_password(client):
    signup(client)
    assert client.post("/api/auth/signup", json={"email": "a@example.com", "password": "password123"}).status_code == 409
    client.cookies.clear()
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrongpass1"}).status_code == 401


def test_short_password_rejected(client):
    assert client.post("/api/auth/signup", json={"email": "b@example.com", "password": "short"}).status_code == 422


def test_cookie_is_httponly(client):
    r = signup(client)
    assert "httponly" in r.headers["set-cookie"].lower()
