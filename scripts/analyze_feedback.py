from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.agents.finance_calibration import load_credit_tier_status
from backend.app.agents.training_feedback import build_training_report


if __name__ == "__main__":
    print(json.dumps(build_training_report(load_credit_tier_status()), indent=2))