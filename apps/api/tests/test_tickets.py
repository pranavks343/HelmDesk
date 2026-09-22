async def _register_and_login(client, email, password="hunter2pass", role="customer"):
    await client.post("/auth/register", json={"email": email, "password": password, "role": role})
    r = await client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_create_and_list_tickets(client):
    token = await _register_and_login(client, "customer1@example.com")
    r = await client.post("/tickets", json={"title": "My printer is on fire"}, headers=_auth(token))
    assert r.status_code == 201, r.text
    ticket = r.json()
    assert ticket["status"] == "open"
    assert ticket["title"] == "My printer is on fire"

    r = await client.get("/tickets", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_customer_cannot_see_others_tickets(client):
    token_a = await _register_and_login(client, "a@example.com")
    token_b = await _register_and_login(client, "b@example.com")
    r = await client.post("/tickets", json={"title": "A's ticket"}, headers=_auth(token_a))
    ticket_id = r.json()["id"]

    r = await client.get("/tickets", headers=_auth(token_b))
    assert r.json() == []

    r = await client.get(f"/tickets/{ticket_id}", headers=_auth(token_b))
    assert r.status_code == 403


async def test_agent_sees_all_tickets(client):
    token_customer = await _register_and_login(client, "c@example.com")
    token_agent = await _register_and_login(client, "agent@example.com", role="agent")
    await client.post("/tickets", json={"title": "ticket 1"}, headers=_auth(token_customer))

    r = await client.get("/tickets", headers=_auth(token_agent))
    assert len(r.json()) == 1


async def test_customer_cannot_update_ticket_status(client):
    token = await _register_and_login(client, "d@example.com")
    r = await client.post("/tickets", json={"title": "t"}, headers=_auth(token))
    ticket_id = r.json()["id"]

    r = await client.patch(f"/tickets/{ticket_id}", json={"status": "resolved"}, headers=_auth(token))
    assert r.status_code == 403


async def test_agent_can_update_ticket_status(client):
    token_customer = await _register_and_login(client, "e@example.com")
    token_agent = await _register_and_login(client, "agent2@example.com", role="agent")
    r = await client.post("/tickets", json={"title": "t"}, headers=_auth(token_customer))
    ticket_id = r.json()["id"]

    r = await client.patch(f"/tickets/{ticket_id}", json={"status": "resolved"}, headers=_auth(token_agent))
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


async def test_ticket_not_found(client):
    token = await _register_and_login(client, "f@example.com")
    r = await client.get("/tickets/00000000-0000-0000-0000-000000000000", headers=_auth(token))
    assert r.status_code == 404


async def test_invalid_ticket_id_format(client):
    token = await _register_and_login(client, "g@example.com")
    r = await client.get("/tickets/not-a-uuid", headers=_auth(token))
    assert r.status_code == 400


async def test_post_and_list_messages(client):
    token = await _register_and_login(client, "h@example.com")
    r = await client.post("/tickets", json={"title": "t"}, headers=_auth(token))
    ticket_id = r.json()["id"]

    r = await client.post(f"/tickets/{ticket_id}/messages", json={"text": "hello"}, headers=_auth(token))
    assert r.status_code == 201, r.text
    assert r.json()["text"] == "hello"

    r = await client.get(f"/tickets/{ticket_id}/messages", headers=_auth(token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["text"] == "hello"


async def test_stranger_cannot_post_message(client):
    token_a = await _register_and_login(client, "i@example.com")
    token_b = await _register_and_login(client, "j@example.com")
    r = await client.post("/tickets", json={"title": "t"}, headers=_auth(token_a))
    ticket_id = r.json()["id"]

    r = await client.post(f"/tickets/{ticket_id}/messages", json={"text": "hi"}, headers=_auth(token_b))
    assert r.status_code == 403
