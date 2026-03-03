from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_root_ok():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json().get("name") == "compras"

def test_ui_requires_login_redirect():
    r = client.get("/ui/mbom", follow_redirects=False)
    # middleware should redirect to login
    assert r.status_code in (302, 307)
    assert "/ui/login" in r.headers.get("location", "")
