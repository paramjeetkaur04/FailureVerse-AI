from app import app


def test_index_identifies_the_test_application():
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert response.json["service"] == "failureverse-demo"


def test_health_is_real_and_timestamped():
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "healthy"
    assert response.json["uptime_seconds"] >= 0
    assert response.json["timestamp"].endswith("+00:00")


def test_no_fault_injection_route_exists():
    assert app.test_client().post("/inject", json={"command": "anything"}).status_code == 404
