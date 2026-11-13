"""Verify an already-running local stack without changing infrastructure."""

import argparse
import json
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


def fetch_json(base: str, path: str, body: dict | None = None):
    request = Request(
        base.rstrip("/") + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        return response.status, json.load(response)


class FrontendAssets(HTMLParser):
    """Find real executable assets so an HTML-only response cannot pass the check."""

    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []
        self.styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("src"):
            self.scripts.append(attributes["src"])
        if tag == "link" and attributes.get("rel") == "stylesheet" and attributes.get("href"):
            self.styles.append(attributes["href"])


def verify_frontend(base: str) -> None:
    with urlopen(base, timeout=5) as response:
        assert response.status == 200
        html = response.read().decode()
        assert "FailureVerse" in html
    assets = FrontendAssets()
    assets.feed(html)
    assert assets.scripts, "Frontend HTML has no executable script"
    asset_checks = [(path, "javascript") for path in assets.scripts]
    asset_checks.extend((path, "text/css") for path in assets.styles)
    for path, expected_type in asset_checks:
        target = urljoin(base.rstrip("/") + "/", path)
        assert urlparse(target).netloc == urlparse(base).netloc, "Unexpected cross-origin frontend asset"
        with urlopen(target, timeout=10) as response:
            assert response.status == 200
            assert expected_type in response.headers.get("Content-Type", ""), f"Incorrect content type for {path}"
            assert response.read(), f"Empty frontend asset: {path}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    verify_frontend(args.frontend)
    status, health = fetch_json(args.frontend, "/api/health")
    assert status == 200 and health["database"] == "connected"
    status, check = fetch_json(args.frontend, "/api/checks", {"source": "manual"})
    assert status == 201 and len(check["services"]) == 3
    assert all(item["status"] == "healthy" for item in check["services"]), check
    status, overview = fetch_json(args.frontend, "/api/overview")
    assert status == 200 and any(item["id"] == check["id"] for item in overview["history"])
    _, config = fetch_json(args.frontend, "/api/config")
    assert config["ai_enabled"] is False and config["docker_control_enabled"] is False
    print("PASS: frontend HTML and JS/CSS assets, API proxy, live readiness, Flask HTTP health, SQLite persistence, public configuration")


if __name__ == "__main__":
    main()
