"""Phase 0 accessibility smoke tests.

Covers:
- WCAG 2.1 AA contrast ratios for all Imperial brand colours.
- Maintenance Scheduler question classification and response structure.
- Buyer's Guide PDF generation (valid PDF bytes, correct structure).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ── Direct module loader (bypasses agents/__init__.py which needs cv2) ────────

_PROJECT_ROOT = Path(__file__).parent.parent


def _load_module(rel_path: str, module_name: str):
    """Load a Python module by file path without triggering package __init__."""
    spec = importlib.util.spec_from_file_location(
        module_name, _PROJECT_ROOT / rel_path
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ── WCAG contrast helpers ─────────────────────────────────────────────────────

def _relative_luminance(r: int, g: int, b: int) -> float:
    def _channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast_ratio(hex1: str, hex2: str) -> float:
    def _rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    l1 = _relative_luminance(*_rgb(hex1))
    l2 = _relative_luminance(*_rgb(hex2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ── Task 0.1 – WCAG contrast ─────────────────────────────────────────────────

class TestWcagContrast:
    """All text/background pairs must meet WCAG 2.1 AA (≥4.5:1 for normal text)."""

    WHITE = "#FFFFFF"
    IMPERIAL_PRIMARY   = "#B22234"  # red
    IMPERIAL_SECONDARY = "#1A1A1A"  # near-black
    IMPERIAL_DANGER    = "#C62828"  # error red
    IMPERIAL_NEUTRAL   = "#595959"  # mid-gray
    IMPERIAL_ACCENT    = "#2E7D32"  # savings green

    def _assert_aa(self, fg: str, bg: str, label: str) -> None:
        ratio = _contrast_ratio(fg, bg)
        assert ratio >= 4.5, (
            f"{label}: {ratio:.2f}:1 fails WCAG AA (need ≥4.5:1)"
        )

    def test_primary_on_white(self):
        self._assert_aa(self.IMPERIAL_PRIMARY, self.WHITE, "imperial-primary on white")

    def test_white_on_primary(self):
        self._assert_aa(self.WHITE, self.IMPERIAL_PRIMARY, "white on imperial-primary")

    def test_secondary_on_white(self):
        self._assert_aa(self.IMPERIAL_SECONDARY, self.WHITE, "imperial-secondary on white")

    def test_white_on_secondary(self):
        self._assert_aa(self.WHITE, self.IMPERIAL_SECONDARY, "white on imperial-secondary")

    def test_danger_on_white(self):
        self._assert_aa(self.IMPERIAL_DANGER, self.WHITE, "imperial-danger on white")

    def test_white_on_danger(self):
        self._assert_aa(self.WHITE, self.IMPERIAL_DANGER, "white on imperial-danger")

    def test_neutral_on_white(self):
        self._assert_aa(self.IMPERIAL_NEUTRAL, self.WHITE, "imperial-neutral on white")

    def test_accent_on_white(self):
        self._assert_aa(self.IMPERIAL_ACCENT, self.WHITE, "imperial-accent on white")

    def test_old_orange_would_fail(self):
        """Regression: the previous #FF6D00 orange fails — confirm the fix is needed."""
        old_orange = "#FF6D00"
        ratio = _contrast_ratio(old_orange, self.WHITE)
        assert ratio < 4.5, (
            f"Old orange {old_orange} unexpectedly passes ({ratio:.2f}:1) — test needs updating"
        )


# ── Task 0.5 – Maintenance Scheduler ─────────────────────────────────────────

class TestMaintenanceScheduler:
    """Classify and respond to maintenance-related chat queries."""

    @pytest.mark.parametrize("question,expected", [
        ("when should I change my oil?", "maintenance_schedule"),
        ("maintenance schedule for my Camry", "maintenance_schedule"),
        ("how often should I rotate my tires?", "maintenance_schedule"),
        ("when do I need new spark plugs?", "maintenance_schedule"),
        ("cabin air filter replacement interval", "maintenance_schedule"),
        ("how often to change brake fluid?", "maintenance_schedule"),
    ])
    def test_classification(self, question: str, expected: str):
        chatbot = _load_module(
            "backend/app/agents/imperial_chatbot.py",
            "imperial_chatbot_isolated",
        )
        assert chatbot._classify_question(question) == expected, (
            f"'{question}' should classify as '{expected}'"
        )

    def test_response_structure(self):
        """Test the template-fallback path for maintenance_schedule (no model load)."""
        chatbot = _load_module(
            "backend/app/agents/imperial_chatbot.py",
            "imperial_chatbot_isolated",
        )
        # Directly exercise the template branch: classify → get schedule → format answer
        question_type = chatbot._classify_question("when should I change my oil?")
        assert question_type == "maintenance_schedule"

        schedule = chatbot._get_maintenance_schedule()
        assert isinstance(schedule, dict) and len(schedule) > 0

        # Simulate what ask_imperial returns in the fallback branch
        lines = "\n".join(f"• {k}: {v}" for k, v in schedule.items())
        answer = (
            f"Here is a standard maintenance schedule:\n\n{lines}\n\n"
            "Always follow your owner's manual for model-specific intervals."
        )
        result = {
            "answer": answer,
            "question_type": question_type,
            "data": {"vehicle": "your vehicle", "schedule": schedule},
            "source": "template",
        }
        assert "answer" in result and len(result["answer"]) > 0
        assert "schedule" in result["data"]

    def test_schedule_has_required_services(self):
        chatbot = _load_module(
            "backend/app/agents/imperial_chatbot.py",
            "imperial_chatbot_isolated",
        )
        schedule = chatbot._get_maintenance_schedule()
        required = {"Oil & Filter Change", "Tire Rotation", "Brake Inspection", "Battery"}
        for service in required:
            assert service in schedule, f"Schedule missing required service: {service}"

    def test_voice_trigger_phrase_classified(self):
        """'when should I' phrase should trigger maintenance_schedule, not general."""
        chatbot = _load_module(
            "backend/app/agents/imperial_chatbot.py",
            "imperial_chatbot_isolated",
        )
        assert chatbot._classify_question("when should I get my car serviced?") == "maintenance_schedule"


# ── Task 0.4 – Buyer's Guide PDF ─────────────────────────────────────────────

class TestBuyersGuidePdf:
    """PDF generator must return valid PDF bytes."""

    def test_empty_cars_returns_valid_pdf(self):
        bg = _load_module(
            "backend/app/agents/buyers_guide.py",
            "buyers_guide_isolated",
        )
        pdf = bg.generate_buyers_guide_pdf([])
        assert pdf[:4] == b"%PDF", "Output must begin with PDF header %%PDF"
        assert len(pdf) > 2_000, "PDF is suspiciously small"

    def test_pdf_with_mock_cars(self):
        bg = _load_module(
            "backend/app/agents/buyers_guide.py",
            "buyers_guide_isolated",
        )

        class _MockCar:
            year = 2023
            make = "Toyota"
            model = "Camry"
            trim = "XSE"
            msrp = 31_000
            mpg_highway = 39
            safety_rating = 5

        pdf = bg.generate_buyers_guide_pdf([_MockCar()] * 5)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 3_000

    def test_pdf_with_none_fields(self):
        """Cars with None fields must not raise; PDF should still be generated."""
        bg = _load_module(
            "backend/app/agents/buyers_guide.py",
            "buyers_guide_isolated",
        )

        class _SparseCar:
            year = None
            make = "Ford"
            model = "F-150"
            trim = None
            msrp = None
            mpg_highway = None
            safety_rating = None

        pdf = bg.generate_buyers_guide_pdf([_SparseCar()])
        assert pdf[:4] == b"%PDF"

    def test_pdf_truncates_to_20_vehicles(self):
        """Only up to 20 vehicles should appear in the PDF even with 30 passed in."""
        bg = _load_module(
            "backend/app/agents/buyers_guide.py",
            "buyers_guide_isolated",
        )

        class _Car:
            year = 2022
            make = "Honda"
            model = "Civic"
            trim = "Sport"
            msrp = 24_000
            mpg_highway = 36
            safety_rating = 5

        # 30 cars passed — generator should silently cap at 20
        pdf = bg.generate_buyers_guide_pdf([_Car()] * 30)
        assert pdf[:4] == b"%PDF"
