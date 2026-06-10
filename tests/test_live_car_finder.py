from __future__ import annotations

from types import SimpleNamespace

import backend.app.skills.live_car_finder as finder


class _Resp:
    def __init__(self, text: str = "", status_code: int = 200, url: str = "https://www.imperialcars.com/test.htm") -> None:
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_find_heated_2500_trucks_success(monkeypatch) -> None:
    html = """
    <html><body>
      <article class='vehicle-card'>
        <h3 class='title'>2024 Ram 2500 Big Horn</h3>
        <div class='price'>$54,995</div>
        <p>Heated front seats and heated steering wheel.</p>
        <a href='/used/Ram/2024-Ram-2500-abcd1234.htm'>View</a>
      </article>
      <article class='vehicle-card'>
        <h3 class='title'>2025 Ford F-250 XLT</h3>
        <div class='price'>$61,250</div>
        <p>Heated seats included.</p>
        <a href='/new/Ford/2025-Ford-F-250-defg5678.htm'>View</a>
      </article>
    </body></html>
    """

    def fake_get(url: str, headers: dict | None = None, timeout: int = 0, allow_redirects: bool = True):
        if "imperialcars.com" in url and "mendon-ma" in url:
            return _Resp(text=html, status_code=200, url=url)
        return _Resp(text="", status_code=200, url=url)

    monkeypatch.setattr(finder.requests, "get", fake_get)
    monkeypatch.setattr(finder.requests, "head", lambda *args, **kwargs: _Resp(status_code=200, url=args[0]))

    matches = finder.LiveCarFinder.find_heated_2500_trucks()

    assert len(matches) == 2
    assert "Ram 2500" in matches[0]["title"]
    assert matches[0]["url"].startswith("https://www.imperialcars.com/")


def test_find_heated_2500_trucks_network_failure(monkeypatch) -> None:
    def fake_get(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(finder.requests, "get", fake_get)
    matches = finder.LiveCarFinder.find_heated_2500_trucks()
    assert matches == []


def test_format_customer_response_fallback() -> None:
    text = finder.LiveCarFinder.format_customer_response([])
    assert "I cannot scrape ImperialCars.com due to access restrictions." in text
    assert "imperialcars.com/chevrolet-ford-ram-trucks-mendon-ma.htm" in text
