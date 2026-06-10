#!/usr/bin/env python3
"""Evaluate base vs sales-finetuned model on a held-out split.

Outputs metric summary and optional human-rating CSV for Streamlit review.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from typing import Any


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    if not rows:
        raise ValueError(f"No rows in {path}")
    return rows


def split_data(rows: list[dict[str, Any]], seed: int = 42) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    copied = list(rows)
    random.Random(seed).shuffle(copied)
    split_index = int(len(copied) * 0.8)
    return copied[:split_index], copied[split_index:]


def safe_generate(model: Any, tokenizer: Any, prompt: str, max_new_tokens: int = 160) -> str:
    import torch

    encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=768)
    if hasattr(model, "device"):
        encoded = {k: v.to(model.device) for k, v in encoded.items()}

    with torch.no_grad():
        output = model.generate(
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    text = tokenizer.decode(output[0], skip_special_tokens=True)
    return text.replace(prompt, "", 1).strip()


def load_model_pair(base_model: str, adapter_path: str | None) -> tuple[Any, Any]:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(base_model, device_map="auto", low_cpu_mem_usage=True)

    if adapter_path and os.path.exists(adapter_path):
        try:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, adapter_path)
        except Exception as exc:
            print(f"[eval] adapter load warning: {exc}")

    model.eval()
    return model, tokenizer


def lexical_similarity(reference: str, prediction: str) -> float:
    ref_tokens = set(str(reference).lower().split())
    pred_tokens = set(str(prediction).lower().split())
    if not ref_tokens:
        return 0.0
    return len(ref_tokens.intersection(pred_tokens)) / float(len(ref_tokens))


def compute_metrics(references: list[str], predictions: list[str]) -> dict[str, float]:
    try:
        import evaluate

        rouge = evaluate.load("rouge")
        bleu = evaluate.load("bleu")
        rouge_scores = rouge.compute(predictions=predictions, references=references)
        bleu_score = bleu.compute(predictions=predictions, references=[[ref] for ref in references])
        return {
            "rougeL": float(rouge_scores.get("rougeL", 0.0)),
            "rouge1": float(rouge_scores.get("rouge1", 0.0)),
            "bleu": float(bleu_score.get("bleu", 0.0)),
        }
    except Exception:
        sims = [lexical_similarity(ref, pred) for ref, pred in zip(references, predictions)]
        avg_sim = sum(sims) / max(1, len(sims))
        return {"lexical_overlap": float(avg_sim)}


def run_streamlit_ui(comparisons_path: str, ratings_path: str) -> None:
    import csv
    import streamlit as st

    if not os.path.exists(comparisons_path):
        st.error(f"Comparisons file not found: {comparisons_path}")
        return

    rows: list[dict[str, str]] = []
    with open(comparisons_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    st.title("Imperial Sales Model Human Evaluation")
    st.write("Choose which answer is better for each instruction.")

    idx = st.number_input("Sample index", min_value=0, max_value=max(0, len(rows) - 1), value=0, step=1)
    row = rows[int(idx)]

    st.subheader("Instruction")
    st.write(row.get("instruction", ""))

    st.subheader("Reference")
    st.write(row.get("reference", ""))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Base")
        st.write(row.get("base_answer", ""))
    with col2:
        st.markdown("### Fine-tuned")
        st.write(row.get("finetuned_answer", ""))

    winner = st.radio("Better answer", ["base", "finetuned", "tie"], index=2, horizontal=True)
    if st.button("Save Rating"):
        os.makedirs(os.path.dirname(ratings_path) or ".", exist_ok=True)
        file_exists = os.path.exists(ratings_path)
        with open(ratings_path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["index", "winner", "instruction"])
            if not file_exists:
                writer.writeheader()
            writer.writerow({"index": int(idx), "winner": winner, "instruction": row.get("instruction", "")})
        st.success("Saved")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate base vs fine-tuned sales model")
    parser.add_argument("--data_path", default=os.path.join("data", "finetune_sales_data.jsonl"))
    parser.add_argument("--base_model", default="deepseek-ai/deepseek-r1-distill-qwen-1.5b")
    parser.add_argument("--adapter_path", default=os.path.join("models", "sales_finetuned"))
    parser.add_argument("--max_eval_samples", type=int, default=50)
    parser.add_argument("--output_path", default=os.path.join("data", "sales_eval_comparisons.jsonl"))
    parser.add_argument("--streamlit", action="store_true", help="Run human-eval UI")
    parser.add_argument("--ratings_path", default=os.path.join("data", "sales_eval_human_ratings.csv"))
    args = parser.parse_args()

    if args.streamlit:
        run_streamlit_ui(args.output_path, args.ratings_path)
        return 0

    rows = load_jsonl(args.data_path)
    _, holdout = split_data(rows)
    holdout = holdout[: max(1, int(args.max_eval_samples))]

    try:
        base_model, base_tokenizer = load_model_pair(args.base_model, None)
        finetuned_model, finetuned_tokenizer = load_model_pair(args.base_model, args.adapter_path)
    except Exception as exc:
        print(f"[eval] model load failed: {exc}")
        return 1

    references: list[str] = []
    base_preds: list[str] = []
    finetuned_preds: list[str] = []
    comparisons: list[dict[str, str]] = []

    for item in holdout:
        instruction = str(item.get("instruction", "")).strip()
        reference = str(item.get("response", "")).strip()
        prompt = (
            "### System:\nYou are an Imperial Cars salesperson.\n\n"
            f"### Instruction:\n{instruction}\n\n"
            "### Response:\n"
        )
        base_answer = safe_generate(base_model, base_tokenizer, prompt)
        finetuned_answer = safe_generate(finetuned_model, finetuned_tokenizer, prompt)

        references.append(reference)
        base_preds.append(base_answer)
        finetuned_preds.append(finetuned_answer)
        comparisons.append(
            {
                "instruction": instruction,
                "reference": reference,
                "base_answer": base_answer,
                "finetuned_answer": finetuned_answer,
            }
        )

    base_metrics = compute_metrics(references, base_preds)
    finetuned_metrics = compute_metrics(references, finetuned_preds)

    os.makedirs(os.path.dirname(args.output_path) or ".", exist_ok=True)
    with open(args.output_path, "w", encoding="utf-8") as handle:
        for row in comparisons:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")

    print("[eval] Base metrics:", json.dumps(base_metrics, indent=2))
    print("[eval] Fine-tuned metrics:", json.dumps(finetuned_metrics, indent=2))
    print(f"[eval] comparison rows saved to {args.output_path}")
    print("[eval] To launch human evaluator: streamlit run scripts/evaluate_sales_model.py -- --streamlit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
