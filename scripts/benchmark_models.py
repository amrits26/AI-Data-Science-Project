#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RESULTS_PATH = os.path.join(DATA_DIR, "benchmark_results.jsonl")
REPORT_PATH = os.path.join(DATA_DIR, "benchmark_report.md")

ASK_URL = "http://127.0.0.1:8000/api/ask"
HEALTH_URL = "http://127.0.0.1:8000/api/health"
REQUEST_TIMEOUT_SECONDS = 30

QUERIES = [
    "Do you have a blue Ford F-150 with a tow package?",
    "Compare the Ford F-150 and Chevy Colorado for towing capacity and fuel economy.",
    "Show me SUVs with 3rd row seating under $35,000.",
    "What's the difference between AWD and 4WD?",
    "How safe is the 2024 Honda CR-V?",
    "Which truck on your lot can tow my 8,000 lb boat and has the best fuel economy?",
    "Is the 2023 Toyota Camry reliable for long-term ownership?",
    "Tell me about the cheapest truck you have.",
    "What's the starting MSRP for a Chevrolet Traverse?",
    "Help me pick between GMC and Ford for a work truck.",
    "I need a car that fits 3 car seats, has AWD, and gets good gas mileage.",
    "Does a used 2022 Lexus RX hold its resale value?",
]


@dataclass
class ModelProfile:
    name: str
    benchmark_model: str


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_inventory_truth() -> dict[str, set[str]]:
    db_path = os.path.join(DATA_DIR, "imperial_cars.db")
    values = {
        "vins": set(),
        "stock_numbers": set(),
        "vehicle_labels": set(),
    }
    if not os.path.exists(db_path):
        return values

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT year, make, model, vin, stock_number FROM cars")
        for year, make, model, vin, stock in cursor.fetchall():
            if vin:
                values["vins"].add(str(vin).strip().upper())
            if stock:
                values["stock_numbers"].add(str(stock).strip().upper())
            label = " ".join([str(part).strip() for part in [year, make, model] if part is not None]).strip().lower()
            if label:
                values["vehicle_labels"].add(label)
    finally:
        conn.close()

    return values


def _wait_for_health(timeout_seconds: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            response = requests.get(HEALTH_URL, timeout=5)
            if response.ok:
                payload = response.json()
                if payload.get("status") in {"ok", "degraded"}:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _preflight_deepseek() -> dict[str, Any]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    ollama_model = os.getenv("DEEPSEEK_OLLAMA_MODEL", "deepseek-r1:7b").strip() or "deepseek-r1:7b"

    if api_key:
        try:
            import openai

            client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                messages=[{"role": "user", "content": "Say OK"}],
                max_tokens=8,
                timeout=60,
            )
            content = ""
            if response.choices and response.choices[0].message:
                content = str(response.choices[0].message.content or "").strip()
            return {
                "ok": True,
                "path": "deepseek_api",
                "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "probe_response": content,
            }
        except Exception as exc:
            return {
                "ok": False,
                "path": "deepseek_api",
                "error": str(exc),
                "hint": "Set a valid DEEPSEEK_API_KEY or unset it to use Ollama fallback.",
            }

    try:
        listed = subprocess.run(
            ["ollama", "list"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "path": "ollama",
            "error": f"Unable to run 'ollama list': {exc}",
            "hint": "Install Ollama and pull deepseek-r1:7b, or configure DEEPSEEK_API_KEY.",
        }

    if listed.returncode != 0:
        return {
            "ok": False,
            "path": "ollama",
            "error": listed.stderr.strip() or listed.stdout.strip() or "ollama list failed",
            "hint": "Ensure Ollama is installed and running.",
        }

    if ollama_model not in listed.stdout:
        return {
            "ok": False,
            "path": "ollama",
            "error": f"Model '{ollama_model}' not found in ollama list.",
            "hint": f"Run: ollama pull {ollama_model}",
        }

    try:
        probe = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": ollama_model, "prompt": "Say OK", "stream": False},
            timeout=60,
        )
        probe.raise_for_status()
        payload = probe.json() if probe.content else {}
        return {
            "ok": True,
            "path": "ollama",
            "model": ollama_model,
            "probe_response": str(payload.get("response", "")).strip(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "path": "ollama",
            "error": str(exc),
            "hint": "Ensure Ollama service is running: ollama serve",
        }


def _start_backend(env: dict[str, str], profile_name: str) -> subprocess.Popen[Any]:
    python_exe = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        raise RuntimeError("Python executable not found at .venv\\Scripts\\python.exe")

    out_log = os.path.join(DATA_DIR, f"benchmark_{profile_name}.out.log")
    err_log = os.path.join(DATA_DIR, f"benchmark_{profile_name}.err.log")
    out_handle = open(out_log, "w", encoding="utf-8", errors="ignore")
    err_handle = open(err_log, "w", encoding="utf-8", errors="ignore")

    proc = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
        env=env,
        stdout=out_handle,
        stderr=err_handle,
    )
    proc._benchmark_out = out_handle  # type: ignore[attr-defined]
    proc._benchmark_err = err_handle  # type: ignore[attr-defined]
    return proc


def _stop_backend(proc: subprocess.Popen[Any] | None) -> None:
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    for attr in ["_benchmark_out", "_benchmark_err"]:
        handle = getattr(proc, attr, None)
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass


def _extract_sources_from_answer(answer: str) -> list[str]:
    match = re.search(r"Sources:\s*(.+?)(?:\.|$)", answer or "", flags=re.IGNORECASE)
    if not match:
        return []
    chunk = match.group(1)
    return [part.strip() for part in chunk.split(",") if part.strip()]


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _score_row(row: dict[str, Any], truth: dict[str, set[str]]) -> dict[str, Any]:
    answer = str(row.get("response", {}).get("answer", ""))
    metadata = row.get("response", {}).get("metadata", {}) if isinstance(row.get("response", {}), dict) else {}
    sources_meta = metadata.get("sources", []) if isinstance(metadata, dict) else []
    if not isinstance(sources_meta, list):
        sources_meta = []

    answer_sources = _extract_sources_from_answer(answer)

    # Vehicle reference correctness
    vehicles = metadata.get("vehicles", []) if isinstance(metadata, dict) else []
    if not isinstance(vehicles, list):
        vehicles = []

    vehicle_correct = 0
    if vehicles:
        label_hits = 0
        for vehicle in vehicles[:3]:
            if not isinstance(vehicle, dict):
                continue
            label = " ".join(
                [
                    str(vehicle.get("year", "")).strip(),
                    str(vehicle.get("make", "")).strip(),
                    str(vehicle.get("model", "")).strip(),
                ]
            ).strip().lower()
            if label and label in truth["vehicle_labels"] and label in answer.lower():
                label_hits += 1
        vehicle_correct = 1 if label_hits > 0 else 0

    # Spec accuracy heuristic: check that at least one structured spec value appears if vehicle exists.
    spec_accuracy = 0
    if vehicles:
        lead = vehicles[0] if isinstance(vehicles[0], dict) else {}
        if isinstance(lead, dict):
            spec_values = [lead.get("horsepower"), lead.get("torque"), lead.get("towing_capacity"), lead.get("mpg_highway")]
            for value in spec_values:
                if value is None:
                    continue
                normalized = str(int(value)) if isinstance(value, (int, float)) else str(value)
                if normalized and normalized in answer:
                    spec_accuracy = 1
                    break

    # Hallucination heuristic for VIN/stock.
    vin_candidates = re.findall(r"\b[A-HJ-NPR-Z0-9]{17}\b", answer.upper())
    stock_candidates = re.findall(r"\b[A-Z0-9-]{5,}\b", answer.upper())
    hallucination = 0
    for vin in vin_candidates:
        if vin not in truth["vins"]:
            hallucination = 1
            break
    if hallucination == 0:
        stock_like = [token for token in stock_candidates if any(ch.isdigit() for ch in token)]
        known_stock = truth["stock_numbers"]
        if known_stock and stock_like and all(token not in known_stock for token in stock_like[:5]):
            hallucination = 1

    # Source attribution correctness
    source_correct = 1
    if answer_sources:
        source_correct = 1 if all(src in sources_meta for src in answer_sources) else 0

    # Fluency heuristic (1-5)
    fluency = 5
    lower = answer.lower()
    if "[question:" in lower or "answer:" in lower:
        fluency = 2
    elif len(answer.strip()) < 40:
        fluency = 2
    elif len(answer.split()) < 18:
        fluency = 3
    elif "sources:" not in lower:
        fluency = 3

    return {
        "vehicle_reference_correct": vehicle_correct,
        "spec_accuracy": spec_accuracy,
        "hallucination": hallucination,
        "source_attribution_correct": source_correct,
        "fluency": fluency,
    }


def _aggregate(rows: list[dict[str, Any]], profile: str) -> dict[str, Any]:
    profile_rows = [row for row in rows if row.get("profile") == profile]
    if not profile_rows:
        return {
            "profile": profile,
            "count": 0,
            "avg_latency_ms": 0.0,
            "vehicle_reference_rate": 0.0,
            "spec_accuracy_rate": 0.0,
            "hallucination_rate": 0.0,
            "source_attribution_rate": 0.0,
            "avg_fluency": 0.0,
            "composite_score": 0.0,
        }

    latencies = [_to_float(row.get("latency_ms")) for row in profile_rows]
    vehicle_scores = [_to_float(row.get("scores", {}).get("vehicle_reference_correct")) for row in profile_rows]
    spec_scores = [_to_float(row.get("scores", {}).get("spec_accuracy")) for row in profile_rows]
    hallucinations = [_to_float(row.get("scores", {}).get("hallucination")) for row in profile_rows]
    source_scores = [_to_float(row.get("scores", {}).get("source_attribution_correct")) for row in profile_rows]
    fluency_scores = [_to_float(row.get("scores", {}).get("fluency")) for row in profile_rows]

    count = len(profile_rows)
    avg_latency = sum(latencies) / count
    vehicle_rate = sum(vehicle_scores) / count
    spec_rate = sum(spec_scores) / count
    hallucination_rate = sum(hallucinations) / count
    source_rate = sum(source_scores) / count
    avg_fluency = sum(fluency_scores) / count

    latency_factor = max(0.0, min(1.0, 1.0 - (avg_latency / 30000.0)))
    composite = (
        vehicle_rate * 0.25
        + spec_rate * 0.2
        + (1.0 - hallucination_rate) * 0.2
        + source_rate * 0.2
        + (avg_fluency / 5.0) * 0.1
        + latency_factor * 0.05
    )

    return {
        "profile": profile,
        "count": count,
        "avg_latency_ms": round(avg_latency, 2),
        "vehicle_reference_rate": round(vehicle_rate, 3),
        "spec_accuracy_rate": round(spec_rate, 3),
        "hallucination_rate": round(hallucination_rate, 3),
        "source_attribution_rate": round(source_rate, 3),
        "avg_fluency": round(avg_fluency, 3),
        "composite_score": round(composite, 3),
    }


def _recommend(current_stats: dict[str, Any], deepseek_stats: dict[str, Any]) -> str:
    current_score = _to_float(current_stats.get("composite_score"))
    deepseek_score = _to_float(deepseek_stats.get("composite_score"))

    if deepseek_score >= current_score + 0.08:
        return "Switch to DeepSeek"
    if current_score >= deepseek_score + 0.08:
        return "Keep current model"
    return "Hybrid"


def _write_jsonl(rows: list[dict[str, Any]]) -> None:
    with open(RESULTS_PATH, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _write_report(rows: list[dict[str, Any]], current_stats: dict[str, Any], deepseek_stats: dict[str, Any], recommendation: str) -> None:
    lines: list[str] = []
    lines.append("# DeepSeek vs Current Model Benchmark")
    lines.append("")
    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append("| Profile | Count | Avg Latency (ms) | Vehicle Ref Rate | Spec Accuracy Rate | Hallucination Rate | Source Attribution Rate | Avg Fluency | Composite |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for stats in [current_stats, deepseek_stats]:
        lines.append(
            "| {profile} | {count} | {avg_latency_ms} | {vehicle_reference_rate} | {spec_accuracy_rate} | {hallucination_rate} | {source_attribution_rate} | {avg_fluency} | {composite_score} |".format(
                **stats
            )
        )

    lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    lines.append(f"**{recommendation}**")
    lines.append("")
    lines.append("## Per Query Snapshot")
    lines.append("")
    lines.append("| Query | Profile | Latency (ms) | Source | Vehicle Ref | Spec Accuracy | Hallucination | Source Attribution | Fluency |")
    lines.append("|---|---|---:|---|---:|---:|---:|---:|---:|")

    for row in rows:
        response = row.get("response", {}) if isinstance(row.get("response"), dict) else {}
        scores = row.get("scores", {}) if isinstance(row.get("scores"), dict) else {}
        lines.append(
            "| {query} | {profile} | {latency} | {source} | {vehicle} | {spec} | {hall} | {attr} | {fluency} |".format(
                query=str(row.get("query", "")).replace("|", "\\|"),
                profile=str(row.get("profile", "")),
                latency=round(_to_float(row.get("latency_ms")), 2),
                source=str(response.get("source", "")),
                vehicle=int(_to_float(scores.get("vehicle_reference_correct"))),
                spec=int(_to_float(scores.get("spec_accuracy"))),
                hall=int(_to_float(scores.get("hallucination"))),
                attr=int(_to_float(scores.get("source_attribution_correct"))),
                fluency=round(_to_float(scores.get("fluency")), 2),
            )
        )

    with open(REPORT_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run_benchmark() -> None:
    _ensure_dirs()
    truth = _load_inventory_truth()

    profiles = [
        ModelProfile(name="current", benchmark_model="current"),
        ModelProfile(name="deepseek", benchmark_model="deepseek"),
    ]

    base_env = dict(os.environ)
    base_env.setdefault("DATABASE_URL", "sqlite:///./data/imperial_cars.db")

    preflight = {
        "deepseek": _preflight_deepseek(),
    }
    if not bool(preflight["deepseek"].get("ok")):
        print(json.dumps({
            "status": "error",
            "phase": "preflight",
            "diagnostics": preflight,
            "message": "DeepSeek connectivity preflight failed. Fix diagnostics and rerun.",
        }, indent=2))
        sys.exit(1)

    rows: list[dict[str, Any]] = []

    for profile in profiles:
        proc: subprocess.Popen[Any] | None = None
        profile_env = dict(base_env)
        profile_env["BENCHMARK_MODEL"] = profile.benchmark_model

        try:
            proc = _start_backend(profile_env, profile.name)
            if not _wait_for_health(timeout_seconds=60):
                for query in QUERIES:
                    rows.append(
                        {
                            "timestamp": int(time.time()),
                            "profile": profile.name,
                            "benchmark_model": profile.benchmark_model,
                            "query": query,
                            "latency_ms": None,
                            "status": "error",
                            "error": "backend_health_timeout",
                            "diagnostics": preflight,
                            "response": {},
                            "scores": {
                                "vehicle_reference_correct": 0,
                                "spec_accuracy": 0,
                                "hallucination": 1,
                                "source_attribution_correct": 0,
                                "fluency": 1,
                            },
                        }
                    )
                continue

            for query in QUERIES:
                started = time.perf_counter()
                status = "ok"
                error = ""
                response_json: dict[str, Any] = {}
                try:
                    response = requests.post(
                        ASK_URL,
                        json={"question": query},
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    response_json = payload if isinstance(payload, dict) else {"answer": str(payload)}
                except Exception as exc:
                    status = "timeout" if "Read timed out" in str(exc) else "error"
                    error = str(exc)

                latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
                row = {
                    "timestamp": int(time.time()),
                    "profile": profile.name,
                    "benchmark_model": profile.benchmark_model,
                    "query": query,
                    "latency_ms": latency_ms,
                    "status": status,
                    "error": error,
                    "diagnostics": preflight,
                    "response": response_json,
                }
                row["scores"] = _score_row(row, truth)
                rows.append(row)
        finally:
            _stop_backend(proc)

    _write_jsonl(rows)

    current_stats = _aggregate(rows, "current")
    deepseek_stats = _aggregate(rows, "deepseek")
    recommendation = _recommend(current_stats, deepseek_stats)
    _write_report(rows, current_stats, deepseek_stats, recommendation)

    print(json.dumps({
        "status": "ok",
        "results_path": RESULTS_PATH,
        "report_path": REPORT_PATH,
        "recommendation": recommendation,
        "current": current_stats,
        "deepseek": deepseek_stats,
    }, indent=2))


if __name__ == "__main__":
    run_benchmark()
