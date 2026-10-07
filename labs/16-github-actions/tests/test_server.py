import pytest

from app import APP_NAME
from app.server import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": APP_NAME}


def test_version_endpoint_reports_build_metadata(client):
    response = client.get("/version")
    assert response.status_code == 200
    body = response.get_json()
    assert body["service"] == APP_NAME
    assert "version" in body
    assert "commit" in body


def test_fare_endpoint_prices_a_trip(client):
    response = client.post(
        "/fare",
        json={"distance_km": 10, "duration_min": 20, "surge": 1.0},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["currency"] == "INR"
    assert body["total"] == 185.0
    assert body["per_rider"] == [185.0]


def test_fare_endpoint_applies_a_coupon_and_splits(client):
    response = client.post(
        "/fare",
        json={
            "distance_km": 10,
            "duration_min": 20,
            "coupon": "FIRST50",
            "riders": 2,
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 92.5
    assert round(sum(body["per_rider"]), 2) == 92.5


def test_fare_endpoint_rejects_an_invalid_trip(client):
    response = client.post("/fare", json={"distance_km": 0, "duration_min": 20})
    assert response.status_code == 400
    assert "distance_km" in response.get_json()["error"]
