#!/usr/bin/env python3
"""
Manual fine-tuning loop for DeepSeek 1.5B with LoRA on CPU/Windows.
Bypasses Hugging Face Trainer to avoid multiprocessing issues.
"""
import argparse
import json
import logging
import math
import os
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
    DataCollatorForLanguageModeling,
)
from torch.optim import AdamW
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training


def _setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("finetune_manual")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def _load_jsonl(path: Path, max_samples: int = 0) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
        if max_samples > 0 and len(rows) >= max_samples:
            break
    return rows


def _row_to_text(row: dict[str, Any]) -> str:
    instruction = str(row.get("instruction", "")).strip()
    output = str(row.get("output", row.get("response", ""))).strip()
    if not instruction or not output:
        return ""
    return (
        "### System:\n"
        "You are Imperial Cars Car Guru. Stay factual, inventory-grounded, and concise.\n\n"
        f"### Instruction:\n{instruction}\n\n"
        f"### Response:\n{output}"
    )


def _resolve_target_modules(raw_modules: str) -> list[str]:
    modules = [m.strip() for m in str(raw_modules).split(",") if m.strip()]
    return modules or ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


class TextDataset(Dataset):
    def __init__(self, texts, tokenizer, max_length):
        self.examples = tokenizer(
            texts,
            truncation=True,
            max_length=max_length,
            padding="max_length",
            return_tensors="pt",
        )
    def __len__(self):
        return self.examples["input_ids"].shape[0]
    def __getitem__(self, idx):
        return {k: v[idx] for k, v in self.examples.items()}


def main():
    parser = argparse.ArgumentParser(description="Manual LoRA fine-tune for DeepSeek on CPU")
    parser.add_argument("--training_data", default="data/finetune_deepseek.jsonl")
    parser.add_argument("--output_dir", default="models/deepseek_finetuned")
    parser.add_argument("--model_name", default="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--max_length", type=int, default=512)
    parser.add_argument("--max_samples", type=int, default=0)
    parser.add_argument("--per_device_train_batch_size", type=int, default=1)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=16)
    parser.add_argument("--save_steps", type=int, default=50)
    parser.add_argument("--save_total_limit", type=int, default=5)
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument(
        "--lora_target_modules",
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
        help="Comma-separated module names for LoRA adapters",
    )
    parser.add_argument("--log_file", default="data/logs/finetune_manual.log")
    args = parser.parse_args()

    logger = _setup_logging(Path(args.log_file))
    logger.info("starting_manual_finetune")

    # Load and preprocess data
    rows = _load_jsonl(Path(args.training_data), max_samples=args.max_samples)
    texts = [_row_to_text(row) for row in rows if _row_to_text(row)]
    if not texts:
        logger.error("No valid training rows.")
        return 1
    logger.info(f"Loaded {len(texts)} training examples.")

    # Tokenizer/model
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dataset = TextDataset(texts, tokenizer, args.max_length)
    dataloader = DataLoader(dataset, batch_size=args.per_device_train_batch_size, shuffle=True, num_workers=0)

    # Model/LoRA
    model = AutoModelForCausalLM.from_pretrained(args.model_name, low_cpu_mem_usage=True)
    target_modules = _resolve_target_modules(args.lora_target_modules)
    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=target_modules,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()
    model.train()

    optimizer = AdamW(model.parameters(), lr=args.learning_rate)
    total_steps = math.ceil(len(dataloader) * args.epochs)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=total_steps)
    loss_fn = torch.nn.CrossEntropyLoss(ignore_index=tokenizer.pad_token_id)

    global_step = 0
    accum_loss = 0.0
    model.zero_grad()
    for epoch in range(int(args.epochs)):
        for step, batch in enumerate(dataloader):
            input_ids = batch["input_ids"]
            attention_mask = batch["attention_mask"]
            labels = input_ids.clone()
            outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
            loss = outputs.loss / args.gradient_accumulation_steps
            loss.backward()
            accum_loss += loss.item()
            if (step + 1) % args.gradient_accumulation_steps == 0 or (step + 1) == len(dataloader):
                optimizer.step()
                scheduler.step()
                model.zero_grad()
                global_step += 1
                logger.info(f"step={global_step} loss={accum_loss:.4f}")
                print(f"step={global_step} loss={accum_loss:.4f}")
                accum_loss = 0.0
                # Save checkpoint
                if global_step % args.save_steps == 0:
                    ckpt_dir = Path(args.output_dir) / f"checkpoint-{global_step}"
                    ckpt_dir.mkdir(parents=True, exist_ok=True)
                    model.save_pretrained(str(ckpt_dir))
                    tokenizer.save_pretrained(str(ckpt_dir))
    # Final save
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    logger.info(f"Training complete. Model saved to {args.output_dir}")
    print(f"Training complete. Model saved to {args.output_dir}")

if __name__ == "__main__":
    main()
