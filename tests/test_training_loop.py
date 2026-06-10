from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from backend.app.agents import imperial_chatbot, negotiation
from backend.app.agents.finance_agent import payment_ladder
from backend.app.agents.finance_calibration import calibrate_credit_tiers, load_credit_tier_status
from backend.app.agents.training_feedback import build_training_report, update_feedback


def test_finance_calibration_and_payment_ladder(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", str(data_dir))

    pd.DataFrame(
        [
            {"credit_tier": "excellent", "annual_rate": 5.0},
            {"credit_tier": "excellent", "annual_rate": 5.4},
            {"credit_tier": "good", "annual_rate": 7.2},
            {"credit_tier": "poor", "annual_rate": 17.8},
        ]
    ).to_csv(data_dir / "deals.csv", index=False)

    result = calibrate_credit_tiers()
    assert result["status"] == "ok"
    assert result["tier_rates"]["A"] == 5.2

    ladder = payment_ladder(30000, 3000, "excellent", 60)
    assert ladder["apr"] == 5.2
    assert ladder["credit_tier_source"].endswith("credit_tiers.json")


def test_ask_imperial_logs_feedback_and_report(tmp_path: Path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", str(data_dir))

    monkeypatch.setattr(
        imperial_chatbot,
        "query_knowledge_base",
        lambda question, top_k=3: {
            "status": "ok",
            "contexts": [{"source": "knowledge_base/winning_scripts.txt", "chunk_index": 0, "text": "Ask a tie-down question."}],
        },
    )

    result = imperial_chatbot.ask_imperial("What financing options can you show me?", prefer_template=True)
    assert result["question_type"] == "financing"
    assert result["interaction_id"]
    assert len(result["knowledge_contexts"]) == 1

    with (data_dir / "feedback.csv").open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["interaction_id"] == result["interaction_id"]
    assert rows[0]["rating"] == "0"

    updated = update_feedback(result["interaction_id"], -1, {"phase": "unit_test"})
    assert updated["status"] == "ok"

    report = build_training_report(load_credit_tier_status())
    assert report["feedback"]["feedback_entries"] == 1
    assert report["feedback"]["top_low_rated"][0]["interaction_id"] == result["interaction_id"]


def test_negotiation_assistant_uses_winning_script(tmp_path: Path, monkeypatch) -> None:
    script_path = tmp_path / "winning_scripts.txt"
    script_path.write_text(
        "[Scenario: objection_monthly_payment]\n"
        "Response: \"If I can keep the payment comfortable and the vehicle right, would that be worth a quick look?\"\n"
        "Principle: Tie-down with service language.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(negotiation, "_WINNING_SCRIPTS_PATH", script_path)
    monkeypatch.setattr(
        negotiation,
        "get_similar_vehicles",
        lambda stock_number, max_results=3: [{"stock_number": "ALT-1", "model": "Equinox", "price": 23995}],
    )

    result = negotiation.negotiation_assistant(
        "Can you get my monthly payment lower?",
        customer_name="Jordan",
        stock_number="STOCK-123",
        year=2022,
        make="Honda",
        model="CR-V",
        key_feature="family-friendly cargo room",
    )

    assert result["intent"] == "monthly_payment"
    assert result["scenario"] == "objection_monthly_payment"
    assert "comfortable" in result["example_script"]
    assert "Jordan" in result["talk_track"]
    assert result["cross_sell_alternatives"][0]["stock_number"] == "ALT-1"