async def _login(client, email="kbuser@example.com"):
    await client.post("/auth/register", json={"email": email, "password": "hunter2pass", "role": "customer"})
    r = await client.post("/auth/login", json={"email": email, "password": "hunter2pass"})
    return r.json()["access_token"]


async def test_kb_search_finds_relevant_article(client):
    token = await _login(client)
    r = await client.get(
        "/kb/search", params={"q": "how do I set up sso"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    hits = r.json()
    assert hits
    assert hits[0]["doc_id"] == "sso-setup"


async def test_kb_search_requires_auth(client):
    r = await client.get("/kb/search", params={"q": "sso"})
    assert r.status_code == 401


async def test_kb_search_no_match_returns_empty(client):
    token = await _login(client, "kbuser2@example.com")
    r = await client.get(
        "/kb/search", params={"q": "zzznonexistentqueryxyz"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json() == []
