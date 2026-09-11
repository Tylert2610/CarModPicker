from fastapi.testclient import TestClient

from app.core.config import settings
from tests.conftest import auth_headers, create_and_login_user, login_user

SCRAPE_URL = f"{settings.API_STR}/crawled-pages/scrape"


def _auth_headers(client: TestClient, username: str) -> dict[str, str]:
    create_and_login_user(client, username)
    return auth_headers(login_user(client, username))


SAMPLE_HTML = """
<html>
  <head>
    <title>Cold Air Intake</title>
    <meta property="og:title" content="Cold Air Intake" />
    <meta property="og:description" content="High-flow cold air intake kit." />
    <meta property="product:price:amount" content="199.99" />
    <meta property="og:image" content="https://cdn.example.com/intake.jpg" />
  </head>
  <body><h1>Cold Air Intake</h1></body>
</html>
"""


def test_scrape_requires_auth(client: TestClient):
    response = client.post(SCRAPE_URL, json={"url": "https://example.com/p/1", "html": SAMPLE_HTML})
    assert response.status_code == 401


def test_scrape_returns_parsed_page(client: TestClient):
    headers = _auth_headers(client, "scrape_user")
    response = client.post(
        SCRAPE_URL,
        json={"url": "https://example.com/p/1?utm_source=x&id=7", "html": SAMPLE_HTML},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["product_url"] == "https://example.com/p/1?id=7"
    assert data["adapter_used"]
    assert data["html_size_bytes"] > 0
    assert len(data["html_sha256"]) == 64
    assert "archived" not in data
    assert "archive_skipped_duplicate" not in data


def test_scrape_rejects_blank_input(client: TestClient):
    headers = _auth_headers(client, "scrape_blank_user")
    response = client.post(SCRAPE_URL, json={"url": "  ", "html": SAMPLE_HTML}, headers=headers)
    assert response.status_code == 400
    response = client.post(SCRAPE_URL, json={"url": "https://example.com/p/1", "html": ""}, headers=headers)
    assert response.status_code == 400


def test_scrape_rejects_oversized_html(client: TestClient, monkeypatch):
    headers = _auth_headers(client, "scrape_big_user")
    monkeypatch.setattr(settings, "CRAWLED_PAGE_MAX_HTML_BYTES", 64)
    response = client.post(SCRAPE_URL, json={"url": "https://example.com/p/1", "html": "x" * 65}, headers=headers)
    assert response.status_code == 413
