#!/usr/bin/env python3
"""Fine-tune DeepSeek adapters with LoRA settings tuned for constrained hardware."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any


def _setup_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("finetune_deepseek")
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


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
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


def train(args: argparse.Namespace) -> int:
    import sys
    import os
    import faulthandler
    faulthandler.enable()
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
        print(f"[train] missing dependency: {exc}")
        print("[train] install with: pip install unsloth torch transformers datasets peft bitsandbytes accelerate")
        return 1

    def _excepthook(exc_type, exc_value, exc_traceback):
        logger = logging.getLogger("finetune_deepseek")
        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = _excepthook

    logger = _setup_logging(Path(args.log_file))
    logger.info("starting_deepseek_finetune")

    training_path = Path(args.training_data)
    if not training_path.exists():
        logger.error("training_data_missing path=%s", training_path)
        return 1

    rows = _load_jsonl(training_path)
    if int(args.max_samples) > 0:
        rows = rows[: int(args.max_samples)]

    texts = [_row_to_text(row) for row in rows]
    texts = [text for text in texts if text]
    if not texts:
        logger.error("no_valid_training_rows path=%s", training_path)
        return 1

    use_cuda = bool(torch.cuda.is_available())
    use_4bit = bool(args.use_4bit and use_cuda)
    if args.use_4bit and not use_cuda:
        logger.warning("4bit_requested_but_no_cuda; falling back to non-quantized CPU load")

    # CPU/Trainer diagnostics
    logger.info("training_rows=%s model_name=%s cuda=%s use_4bit=%s", len(texts), args.model_name, use_cuda, use_4bit)
    logger.info("torch_version=%s transformers_version=%s pid=%s", torch.__version__, __import__('transformers').__version__, os.getpid())
    logger.info("effective_batch_size=%s", int(args.per_device_train_batch_size) * int(args.gradient_accumulation_steps))

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quant_config = None
    if use_4bit:
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=quant_config,
        device_map="auto" if use_cuda else "cpu",
        torch_dtype=torch.float16 if use_cuda else None,
        low_cpu_mem_usage=True,
    )

    if use_4bit:
        model = prepare_model_for_kbit_training(model)

    # Auto-disable gradient checkpointing on CPU unless explicitly forced
    gradient_checkpointing = bool(args.gradient_checkpointing)
    if not use_cuda and gradient_checkpointing:
        logger.warning("Auto-disabling gradient checkpointing on CPU for stability. Use --gradient_checkpointing to force enable.")
        gradient_checkpointing = False

    if gradient_checkpointing:
        model.gradient_checkpointing_enable()
        model.config.use_cache = False

    target_modules = _resolve_target_modules(args.lora_target_modules)
    lora_cfg = LoraConfig(
        r=int(args.lora_r),
        lora_alpha=int(args.lora_alpha),
        target_modules=target_modules,
        lora_dropout=float(args.lora_dropout),
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
            max_length=int(args.max_length),
            padding="max_length",
        )
        encoded["labels"] = [list(ids) for ids in encoded["input_ids"]]
        return encoded

    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=float(args.epochs),
        per_device_train_batch_size=int(args.per_device_train_batch_size),
        gradient_accumulation_steps=int(args.gradient_accumulation_steps),
        learning_rate=float(args.learning_rate),
        logging_steps=int(args.logging_steps),
        save_steps=int(args.save_steps),
        save_strategy="steps",
        save_total_limit=int(args.save_total_limit),
        report_to="none",
        bf16=False,
        fp16=bool(use_cuda),
        gradient_checkpointing=gradient_checkpointing,
        dataloader_num_workers=0,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=collator,
    )

    logger.info("trainer_start")
    try:
        trainer.train()
    except Exception as exc:
        logger.exception("trainer.train() failed")
        with open(str(output_dir / "TRAINING_FAILED.txt"), "w", encoding="utf-8") as failf:
            import traceback
            failf.write(traceback.format_exc())
        return 2

    logger.info("trainer_train_complete")
    try:
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))
    except Exception as exc:
        logger.exception("model/tokenizer save failed")
        return 3
    logger.info("model_tokenizer_save_complete")

    meta = {
        "model_name": args.model_name,
        "training_data": str(training_path),
        "samples": len(texts),
        "max_length": int(args.max_length),
        "per_device_train_batch_size": int(args.per_device_train_batch_size),
        "gradient_accumulation_steps": int(args.gradient_accumulation_steps),
        "gradient_checkpointing": gradient_checkpointing,
        "save_steps": int(args.save_steps),
        "learning_rate": float(args.learning_rate),
        "lora_r": int(args.lora_r),
        "lora_alpha": int(args.lora_alpha),
        "lora_dropout": float(args.lora_dropout),
        "lora_target_modules": target_modules,
        "use_4bit": bool(use_4bit),
        "cuda": bool(use_cuda),
    }
    with open(output_dir / "training_meta.json", "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    logger.info("trainer_complete output_dir=%s", output_dir)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune DeepSeek (LoRA) for Imperial Cars")
    parser.add_argument("--training_data", default="data/finetune_deepseek.jsonl")
    parser.add_argument("--output_dir", default="models/deepseek_finetuned")
    parser.add_argument("--model_name", default="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    parser.add_argument("--max_length", type=int, default=512)
    parser.add_argument("--max_samples", type=int, default=0)
    parser.add_argument("--per_device_train_batch_size", type=int, default=1)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=16)
    parser.add_argument("--gradient_checkpointing", action="store_true", default=True)
    parser.add_argument("--no-gradient-checkpointing", action="store_false", dest="gradient_checkpointing")
    parser.add_argument("--save_steps", type=int, default=50)
    parser.add_argument("--save_total_limit", type=int, default=5)
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--use_4bit", action="store_true", default=True)
    parser.add_argument("--no-use_4bit", action="store_false", dest="use_4bit")
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument(
        "--lora_target_modules",
        default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
        help="Comma-separated module names for LoRA adapters",
    )
    parser.add_argument("--log_file", default="data/logs/finetune_deepseek.log")
    args = parser.parse_args()

    try:
        return train(args)
    except Exception as exc:
        print(f"[train] failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
