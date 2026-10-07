import pytest

from app.main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_home_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"hw-devsecops" in r.data


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "healthy"


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ready"


def test_status_fields(client):
    data = client.get("/api/status").get_json()
    assert data["app"] == "hw-devsecops"
    assert data["status"] == "running"
    assert {"version", "git_sha", "python_version", "uptime_seconds"} <= data.keys()


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_greet(client):
    r = client.get("/api/greet/Shaurya")
    assert r.status_code == 200
    assert "Shaurya" in r.get_json()["message"]


@pytest.mark.parametrize("name", ["<script>", "a" * 65, "x;rm -rf"])
def test_greet_rejects_bad_input(client, name):
    assert client.get(f"/api/greet/{name}").status_code == 400


@pytest.mark.parametrize(
    "op,a,b,expected",
    [("add", 2, 3, 5), ("subtract", 9, 4, 5), ("multiply", 6, 3, 18), ("divide", 9, 3, 3)],
)
def test_calculate(client, op, a, b, expected):
    r = client.post("/api/calculate", json={"a": a, "b": b, "operation": op})
    assert r.status_code == 200
    assert r.get_json()["result"] == expected


def test_calculate_divide_by_zero(client):
    r = client.post("/api/calculate", json={"a": 1, "b": 0, "operation": "divide"})
    assert r.status_code == 400


def test_calculate_bad_operation(client):
    r = client.post("/api/calculate", json={"a": 1, "b": 2, "operation": "pow"})
    assert r.status_code == 400


def test_calculate_requires_json(client):
    assert client.post("/api/calculate", data="nope").status_code == 400
    assert client.post("/api/calculate", json={"a": "x", "b": 1}).status_code == 400


def test_404_is_json(client):
    r = client.get("/does-not-exist")
    assert r.status_code == 404
    assert r.get_json()["error"] == "route not found"
