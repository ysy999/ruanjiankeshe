def test_health_returns_200(app_client):
    response = app_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
