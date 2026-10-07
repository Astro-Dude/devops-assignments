import pytest

from app.main import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_index_lists_operations(client):
    body = client.get("/").get_json()
    assert body["service"] == "s16-calculator"
    assert body["operations"] == ["add", "divide", "multiply", "subtract"]


@pytest.mark.parametrize(
    "operation,a,b,expected",
    [("add", 2, 3, 5), ("subtract", 9, 4, 5), ("multiply", 6, 7, 42), ("divide", 9, 2, 4.5)],
)
def test_operations(client, operation, a, b, expected):
    resp = client.get(f"/api/{operation}?a={a}&b={b}")
    assert resp.status_code == 200
    assert resp.get_json()["result"] == expected


def test_divide_by_zero_returns_400(client):
    resp = client.get("/api/divide?a=1&b=0")
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Cannot divide by zero"


def test_unknown_operation_returns_404(client):
    assert client.get("/api/power?a=2&b=3").status_code == 404


def test_missing_parameter_returns_400(client):
    assert client.get("/api/add?a=2").status_code == 400


def test_non_numeric_parameter_returns_400(client):
    assert client.get("/api/add?a=two&b=3").status_code == 400
