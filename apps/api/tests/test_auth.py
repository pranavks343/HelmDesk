

async def _register_and_login(client, email="alice@example.com", password="hunter2pass", role="customer"):
    r = await client.post("/auth/register", json={"email": email, "password": password, "role": role})
    assert r.status_code == 201, r.text
    r = await client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


async def test_register_and_login(client):
    tokens = await _register_and_login(client)
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"


async def test_duplicate_email_rejected(client):
    await _register_and_login(client, email="dup@example.com")
    r = await client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "anotherpass1", "role": "customer"}
    )
    assert r.status_code == 409


async def test_wrong_password_rejected(client):
    await _register_and_login(client, email="bob@example.com", password="correctpass1")
    r = await client.post("/auth/login", json={"email": "bob@example.com", "password": "wrongpass1"})
    assert r.status_code == 401


async def test_refresh_token_issues_new_access_token(client):
    tokens = await _register_and_login(client, email="carol@example.com")
    r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_access_token_rejected_as_refresh(client):
    tokens = await _register_and_login(client, email="dave@example.com")
    r = await client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert r.status_code == 401


async def test_protected_route_requires_token(client):
    r = await client.get("/tickets")
    assert r.status_code == 401
