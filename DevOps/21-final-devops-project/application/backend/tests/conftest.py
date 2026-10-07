"""Test fixtures: every test gets a fresh, throw-away SQLite database.

The production PostgreSQL database is never touched; DATABASE_URL is
overridden before the application is imported.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///./pytest-tickethub.db"
os.environ["APP_ENV"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def ticket(client):
    response = client.post(
        "/api/tickets",
        json={"subject": "VPN keeps disconnecting", "requester": "asha@example.com", "category": "NETWORK"},
    )
    assert response.status_code == 201
    return response.json()


def pytest_sessionfinish(session, exitstatus):
    if os.path.exists("pytest-tickethub.db"):
        os.remove("pytest-tickethub.db")
