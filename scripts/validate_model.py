from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.app.agents.imperial_chatbot import ask_imperial


QUESTIONS = [
    "What is the towing capacity of a 2022 Ford F-150?",
    "Do you have any Chevy Silverados under $45k on the lot?",
    "What’s the interest rate for someone with a 700 credit score?",
    "Compare Ram 1500 vs Ford F-150.",
    "Can I trade in a car with negative equity?",
    "What is the warranty on a used Toyota Camry?",
    "How much is a 2023 GMC Sierra 1500 elevation?",
    "What’s the difference between AWD and 4WD?",
    "Do you offer zero-down financing?",
    "How many miles per gallon does a 2022 Chevy Equinox get?",
    "Is the 2024 Ford Bronco good for a family?",
    "What’s the cost to register a car in Massachusetts?",
    "How does a lease work?",
    "What are the pros of the Toyota RAV4?",
    "Do you have any 2021 Honda CR-Vs?",
    "What is the best SUV for snow?",
    "How long does financing approval take?",
    "Can I get a rebate on a new Chevy?",
    "What’s the difference between a V6 and a V8?",
    "Is it better to buy or lease?",
]


def _ask_rating(index: int) -> int:
    while True:
        try:
            raw = input(f"Rate answer for Q{index} (1-5): ").strip()
        except EOFError:
            return 3
        if not raw:
            return 3
        try:
            rating = int(raw)
        except ValueError:
            print("Enter a number from 1 to 5.")
            continue
        if 1 <= rating <= 5:
            return rating
        print("Enter a number from 1 to 5.")


def main() -> int:
    output_path = PROJECT_ROOT / "data" / "validation_feedback.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    print("=" * 72)
    print("MODEL VALIDATION - 20 QUESTION CHECK")
    print("=" * 72)

    interactive = sys.stdin.isatty()
    for idx, question in enumerate(QUESTIONS, start=1):
        result = ask_imperial(question=question, prefer_template=False)
        answer = str(result.get("answer", ""))
        print("-" * 72)
        print(f"Q{idx}: {question}")
        print(f"A{idx}: {answer}")

        rating = _ask_rating(idx) if interactive else 3
        rows.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "question_index": idx,
                "question": question,
                "answer": answer,
                "rating": rating,
            }
        )

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "question_index", "question", "answer", "rating"])
        writer.writeheader()
        writer.writerows(rows)

    low = [row for row in rows if int(row["rating"]) <= 2]
    print("=" * 72)
    print(f"Saved validation feedback -> {output_path}")
    print(f"Low-rated answers (<=2): {len(low)}")
    if low:
        print("Recommendation: add corrected responses to knowledge_base/winning_scripts.txt and rerun merge + finetune + validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())