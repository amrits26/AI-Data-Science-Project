#!/usr/bin/env python3
"""Fine-tune a sales-style adapter with LoRA on Imperial dealership conversational data."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any


def load_jsonl(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Training data not found: {path}")

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
        raise ValueError(f"No valid rows in {path}")
    return rows


def build_prompt(instruction: str, response: str) -> str:
    return (
        "### System:\n"
        "You are an Imperial Cars salesperson. Be conversational, confident, and helpful.\n\n"
        "### Instruction:\n"
        f"{instruction.strip()}\n\n"
        "### Response:\n"
        f"{response.strip()}"
    )


def train(args: argparse.Namespace) -> int:
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except Exception as exc:
        print(f"[finetune] missing dependency: {exc}")
        print("[finetune] install: pip install torch transformers datasets peft bitsandbytes accelerate")
        return 1

    rows = load_jsonl(args.data_path)
    if int(args.max_samples) > 0:
        rows = rows[: int(args.max_samples)]
    texts = [build_prompt(str(r.get("instruction", "")), str(r.get("response", ""))) for r in rows]

    base_model = args.base_model
    print(f"[finetune] base_model={base_model}")
    print(f"[finetune] samples={len(texts)}")

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_config = None
    device_map: Any = "auto"
    if torch.cuda.is_available():
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
    else:
        device_map = "cpu"

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quant_config,
        device_map=device_map,
        torch_dtype=torch.float16 if torch.cuda.is_available() else None,
        low_cpu_mem_usage=True,
    )

    if quant_config is not None:
        model = prepare_model_for_kbit_training(model)

    lora_cfg = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    dataset = Dataset.from_dict({"text": texts})

    def tokenize(batch: dict[str, list[str]]) -> dict[str, Any]:
        encoded = tokenizer(
            batch["text"],
            truncation=True,
            max_length=768,
            padding="max_length",
        )
        encoded["labels"] = [list(ids) for ids in encoded["input_ids"]]
        return encoded

    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    os.makedirs(args.output_dir, exist_ok=True)
    train_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=max(1, int(args.batch_size)),
        gradient_accumulation_steps=4,
        learning_rate=float(args.learning_rate),
        num_train_epochs=float(args.epochs),
        logging_steps=10,
        save_strategy="epoch",
        report_to="none",
        fp16=torch.cuda.is_available(),
        bf16=False,
    )

    trainer = Trainer(
        model=model,
        args=train_args,
        train_dataset=tokenized,
        data_collator=collator,
    )

    trainer.train()
    model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    with open(os.path.join(args.output_dir, "sales_finetune_meta.json"), "w", encoding="utf-8") as handle:
        json.dump(
            {
                "base_model": base_model,
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "samples": len(texts),
                "adapter_type": "lora",
                "target_modules": ["q_proj", "v_proj"],
                "rank": 16,
                "alpha": 32,
            },
            handle,
            indent=2,
        )

    print(f"[finetune] adapter saved to {args.output_dir}")
    print("[finetune] To merge for faster inference, load base+adapter and call model.merge_and_unload() via PEFT.")
    print("[finetune] Or load adapter dynamically with PeftModel.from_pretrained(base_model, adapter_dir).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LoRA fine-tune for Imperial sales style")
    parser.add_argument("--data_path", default=os.path.join("data", "finetune_sales_data.jsonl"))
    parser.add_argument("--output_dir", default=os.path.join("models", "sales_finetuned"))
    parser.add_argument("--base_model", default="deepseek-ai/deepseek-r1-distill-qwen-1.5b")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--max_samples", type=int, default=0)
    args = parser.parse_args()

    try:
        return train(args)
    except Exception as exc:
        print(f"[finetune] failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
