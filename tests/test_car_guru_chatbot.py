from __future__ import annotations

from fastapi.testclient import TestClient

import backend.app.agents.imperial_chatbot as bot
import backend.app.api.routes as routes
from backend.app.main import app


def test_ask_imperial_detailed_combines_sources_without_db(monkeypatch) -> None:
    monkeypatch.setattr(bot, "_structured_inventory_search", lambda entities, constraints, limit=5: {
        "total": 1,
        "rows": [
            {
                "id": 1,
                "year": 2021,
                "make": "Ford",
                "model": "F-150",
                "trim": "XLT",
                "price": 39995.0,
                "mileage": 22111,
                "color": "Blue",
                "horsepower": 400,
                "torque": 500,
                "towing_capacity": 13000,
                "mpg_highway": 24.0,
                "vin": "TESTVIN1234567890",
            }
        ],
    })
    monkeypatch.setattr(bot, "query_knowledge_base", lambda question, top_k=4: {
        "status": "ok",
        "top_score": 0.88,
        "contexts": [{"source": "wikipedia_ford_f150.txt", "text": "The Ford F-150 is a full-size pickup truck."}],
    })
    monkeypatch.setattr(bot, "fetch_nhtsa", lambda **kwargs: {"status": "ok", "safety": {"OverallRating": "5"}, "recalls": []})
    monkeypatch.setattr(bot, "fetch_fueleconomy", lambda **kwargs: {"status": "ok", "vehicle": {"comb08": "21", "annualfuelcost": "2450"}})
    monkeypatch.setattr(bot, "fetch_kbb", lambda **kwargs: {"status": "not_configured"})
    monkeypatch.setattr(bot, "fetch_carfax", lambda **kwargs: {"status": "not_configured"})

    result = bot.ask_imperial_detailed("Tell me everything about the blue F-150 with the tow package", {})

    assert result["question_type"] in {"inventory_search", "general_knowledge"}
    assert result["source"] in {"inventory", "multi_source"}
    assert "Ford F-150" in result["answer"]
    assert "Sources:" in result["answer"]
    assert "Live Inventory" in result["metadata"]["sources"]
    assert "NHTSA" in result["metadata"]["sources"]


def test_api_ask_returns_multi_source_metadata(monkeypatch) -> None:
    monkeypatch.setattr(bot, "query_knowledge_base", lambda question, top_k=4: {
        "status": "ok",
        "top_score": 0.91,
        "contexts": [{"source": "wikipedia_awd.txt", "text": "AWD sends power to all four wheels for improved traction."}],
    })
    monkeypatch.setattr(bot, "_structured_inventory_search", lambda entities, constraints, limit=5: {"total": 0, "rows": []})
    monkeypatch.setattr(bot, "fetch_nhtsa", lambda **kwargs: {"status": "error", "error": "not needed"})
    monkeypatch.setattr(bot, "fetch_fueleconomy", lambda **kwargs: {"status": "error", "error": "not needed"})
    monkeypatch.setattr(bot, "fetch_kbb", lambda **kwargs: {"status": "not_configured"})
    monkeypatch.setattr(bot, "fetch_carfax", lambda **kwargs: {"status": "not_configured"})

    client = TestClient(app, base_url="http://localhost")
    response = client.post("/api/ask", json={"question": "What is AWD?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["question_type"] == "general_knowledge"
    assert payload["metadata"]["sources"] == ["Knowledge Base", "Wikipedia"]
    assert payload["answer"].endswith("Sources: Knowledge Base, Wikipedia.")


def test_car_finder_mode_returns_live_links(monkeypatch) -> None:
    monkeypatch.setattr(
        bot.LiveCarFinder,
        "find_heated_2500_trucks",
        lambda: [
            {
                "title": "2024 Ram 2500 Big Horn",
                "price": "$54,995",
                "url": "https://www.imperialcars.com/used/Ram/2024-Ram-2500-abcd1234.htm",
            }
        ],
    )

    result = bot.ask_imperial_detailed("Find me a Ram 2500 with heated seats on ImperialCars.com", {})

    assert result["question_type"] == "car_finder"
    assert result["source"] == "live_car_finder"
    assert "I found these 2500-class trucks" in result["answer"]
    assert "https://www.imperialcars.com/used/Ram/2024-Ram-2500-abcd1234.htm" in result["answer"]


def test_car_finder_api_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        routes.LiveCarFinder,
        "find_heated_2500_trucks",
        lambda: [
            {
                "title": "2025 Ford F-250 XLT",
                "price": "$61,250",
                "url": "https://www.imperialcars.com/new/Ford/2025-Ford-F-250-defg5678.htm",
            }
        ],
    )

    client = TestClient(app, base_url="http://localhost")
    response = client.get("/api/car-finder", params={"query": "f-250 heated seats"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["count"] == 1
    assert payload["matches"][0]["title"] == "2025 Ford F-250 XLT"