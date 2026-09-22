from core.config import settings


def _internal_headers():
    return {"X-Internal-Token": settings.internal_service_token}


async def _register_and_login(client, email="cust@example.com"):
    await client.post("/auth/register", json={"email": email, "password": "hunter2pass", "role": "customer"})
    r = await client.post("/auth/login", json={"email": email, "password": "hunter2pass"})
    return r.json()["access_token"]


async def test_internal_endpoints_reject_missing_token(client):
    r = await client.patch(
        "/internal/tickets/00000000-0000-0000-0000-000000000000", json={"status": "resolved"}
    )
    assert r.status_code == 401


async def test_internal_endpoints_reject_wrong_token(client):
    r = await client.patch(
        "/internal/tickets/00000000-0000-0000-0000-000000000000",
        json={"status": "resolved"},
        headers={"X-Internal-Token": "wrong"},
    )
    assert r.status_code == 401


async def test_internal_update_ticket(client):
    token = await _register_and_login(client)
    r = await client.post("/tickets", json={"title": "t"}, headers={"Authorization": f"Bearer {token}"})
    ticket_id = r.json()["id"]

    r = await client.patch(
        f"/internal/tickets/{ticket_id}",
        json={"status": "triaged", "priority": "high", "ai_summary": "billing issue"},
        headers=_internal_headers(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "triaged"
    assert body["priority"] == "high"
    assert body["ai_summary"] == "billing issue"


async def test_internal_update_ticket_not_found(client):
    r = await client.patch(
        "/internal/tickets/00000000-0000-0000-0000-000000000000",
        json={"status": "resolved"},
        headers=_internal_headers(),
    )
    assert r.status_code == 404


async def test_internal_post_message(client):
    token = await _register_and_login(client, "cust2@example.com")
    r = await client.post("/tickets", json={"title": "t"}, headers={"Authorization": f"Bearer {token}"})
    ticket_id = r.json()["id"]

    r = await client.post(
        f"/internal/tickets/{ticket_id}/messages",
        json={"text": "here is a drafted reply", "sender": "ai_agent"},
        headers=_internal_headers(),
    )
    assert r.status_code == 201, r.text
    assert r.json()["sender"] == "ai_agent"

    r = await client.get(f"/tickets/{ticket_id}/messages", headers={"Authorization": f"Bearer {token}"})
    assert len(r.json()) == 1
    assert r.json()[0]["sender"] == "ai_agent"
