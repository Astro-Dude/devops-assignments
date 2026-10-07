def test_health_is_up(client):
    assert client.get("/health").json() == {"status": "UP"}


def test_ready_checks_database(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "READY"}


def test_info_reports_environment(client):
    body = client.get("/api/info").json()
    assert body["service"] == "TicketHub API"
    assert body["environment"] == "test"


def test_create_ticket_defaults(client):
    response = client.post(
        "/api/tickets", json={"subject": "Laptop will not boot", "requester": "ravi@example.com"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "OPEN"
    assert body["priority"] == "MEDIUM"
    assert body["team"] == "L1 Support"


def test_create_ticket_rejects_invalid_priority(client):
    response = client.post(
        "/api/tickets", json={"subject": "Bad priority", "requester": "x@example.com", "priority": "P0"}
    )
    assert response.status_code == 422


def test_create_ticket_rejects_short_subject(client):
    response = client.post("/api/tickets", json={"subject": "no", "requester": "x@example.com"})
    assert response.status_code == 422


def test_list_and_filter_tickets(client):
    client.post("/api/tickets", json={"subject": "Printer jam", "requester": "a", "priority": "LOW"})
    client.post("/api/tickets", json={"subject": "Prod DB down", "requester": "b", "priority": "URGENT"})
    assert len(client.get("/api/tickets").json()) == 2
    urgent = client.get("/api/tickets", params={"priority": "URGENT"}).json()
    assert [t["subject"] for t in urgent] == ["Prod DB down"]
    search = client.get("/api/tickets", params={"q": "printer"}).json()
    assert len(search) == 1


def test_get_ticket_and_404(client, ticket):
    assert client.get(f"/api/tickets/{ticket['id']}").json()["subject"] == "VPN keeps disconnecting"
    assert client.get("/api/tickets/9999").status_code == 404


def test_update_ticket_status(client, ticket):
    response = client.put(f"/api/tickets/{ticket['id']}", json={"status": "IN_PROGRESS", "team": "Network"})
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"
    assert response.json()["team"] == "Network"


def test_delete_ticket(client, ticket):
    assert client.delete(f"/api/tickets/{ticket['id']}").status_code == 204
    assert client.get(f"/api/tickets/{ticket['id']}").status_code == 404
    assert client.delete(f"/api/tickets/{ticket['id']}").status_code == 404


def test_comments_round_trip(client, ticket):
    url = f"/api/tickets/{ticket['id']}/comments"
    assert client.post(url, json={"author": "agent-1", "body": "Rebooted the router"}).status_code == 201
    comments = client.get(url).json()
    assert len(comments) == 1
    assert comments[0]["body"] == "Rebooted the router"


def test_stats_counts_by_status(client):
    for subject, priority in [("One", "URGENT"), ("Two", "URGENT"), ("Three", "LOW")]:
        client.post(
            "/api/tickets", json={"subject": f"Ticket {subject}", "requester": "r", "priority": priority}
        )
    client.put("/api/tickets/1", json={"status": "RESOLVED"})
    stats = client.get("/api/stats").json()
    assert stats == {
        "total": 3,
        "open": 2,
        "in_progress": 0,
        "resolved": 1,
        "closed": 0,
        "urgent_open": 1,
    }


def test_metrics_endpoint_exposes_prometheus_format(client, ticket):
    client.get("/api/tickets")
    body = client.get("/metrics").text
    assert "tickethub_http_requests_total" in body
    assert 'tickethub_tickets_open{priority="MEDIUM"} 1.0' in body
    assert "tickethub_tickets_created_total" in body
