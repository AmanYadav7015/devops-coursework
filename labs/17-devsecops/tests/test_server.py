import pytest

from app.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_version_endpoint_reports_build_metadata(client):
    body = client.get("/version").get_json()
    assert body["service"] == "claim-check-api"
    assert "version" in body
    assert "commit" in body


def test_validate_endpoint_accepts_a_claim(client):
    response = client.post(
        "/claims/validate",
        json={"employee": "asha", "category": "travel", "amount": 500, "receipts": 1},
    )
    assert response.status_code == 200
    assert response.get_json()["valid"] is True


def test_validate_endpoint_rejects_a_bad_claim(client):
    response = client.post("/claims/validate", json={"employee": "asha"})
    assert response.status_code == 400
    assert "category" in response.get_json()["error"]


def test_price_endpoint_prices_a_claim(client):
    response = client.post(
        "/claims/price",
        json={"employee": "asha", "category": "meals", "amount": 1000, "receipts": 2},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["reimbursed"] == 800.0
    assert body["reference"].startswith("CLM-")
    assert len(body["fingerprint"]) == 32


def test_batch_endpoint_summarises(client):
    response = client.post(
        "/claims/batch",
        json={
            "claims": [
                {"employee": "a", "category": "meals", "amount": 500, "receipts": 1},
                {"employee": "b", "category": "meals", "amount": 500, "receipts": 1},
            ]
        },
    )
    assert response.status_code == 200
    assert response.get_json()["total_reimbursed"] == 800.0


def test_batch_endpoint_rejects_an_empty_body(client):
    assert client.post("/claims/batch", json={}).status_code == 400


def test_policy_endpoint_parses_yaml(client):
    response = client.post(
        "/policy/apply",
        data="meals: 1500\ntravel: 12000\n",
        content_type="text/plain",
    )
    assert response.status_code == 200
    assert response.get_json()["entries"] == 2


def test_policy_endpoint_rejects_broken_yaml(client):
    response = client.post(
        "/policy/apply", data="meals: [1, 2\n", content_type="text/plain"
    )
    assert response.status_code == 400


def test_fx_endpoint_reports_no_upstream(client):
    response = client.get("/fx")
    assert response.status_code == 503
