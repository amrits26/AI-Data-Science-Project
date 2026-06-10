from __future__ import annotations

import argparse
import json
import os
from typing import Any


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _pick_question(item: dict[str, Any]) -> str:
    for key in ("question", "instruction", "prompt", "input", "query"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _pick_answer(item: dict[str, Any]) -> str:
    output = item.get("output")
    if isinstance(output, str) and output.strip():
        return output.strip()

    if isinstance(output, dict):
        for key in ("answer", "text", "response", "content"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for key in ("answer", "response", "text", "completion"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _to_chunk(question: str, answer: str) -> str:
    return f"Question: {question}\nAnswer: {answer}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare knowledge_base/auto_qa.txt from QA JSONL data.")
    parser.add_argument(
        "--input",
        default=os.path.join("data", "north_america_auto_qa_2000.jsonl"),
        help="Path to JSONL QA dataset",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("knowledge_base", "auto_qa.txt"),
        help="Output text file consumed by KB ingestion",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to output file instead of overwrite",
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return 1

    rows = _read_jsonl(input_path)
    chunks: list[str] = []
    skipped = 0
    for item in rows:
        question = _pick_question(item)
        answer = _pick_answer(item)
        if not question or not answer:
            skipped += 1
            continue
        chunks.append(_to_chunk(question, answer))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mode = "a" if args.append else "w"
    with open(output_path, mode, encoding="utf-8") as handle:
        if args.append and os.path.getsize(output_path) > 0:
            handle.write("\n")
        for block in chunks:
            handle.write(block)
            handle.write("\n")

    print(f"Wrote {len(chunks)} QA chunks to: {output_path}")
    print(f"Skipped {skipped} malformed rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
