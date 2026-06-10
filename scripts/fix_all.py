#!/usr/bin/env python
"""One-click fixer for Imperial Cars AI environment and service readiness."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def run(cmd: list[str], timeout: int = 120, cwd: Path | None = None) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode == 0, output.strip()
    except Exception as exc:
        return False, str(exc)


def check_env() -> list[str]:
    required = ["DATABASE_URL", "OLLAMA_BASE_URL", "OLLAMA_MODEL"]
    missing = [name for name in required if not os.getenv(name)]
    return missing


def ensure_dependencies(python_exe: str) -> tuple[bool, str]:
    return run([python_exe, "-m", "pip", "install", "-r", "requirements.txt"], timeout=1800)


def ensure_docker_postgres() -> tuple[bool, str]:
    ok, out = run(["docker", "compose", "up", "-d", "postgres"], timeout=300)
    return ok, out


def ensure_database_connectivity(python_exe: str) -> tuple[bool, str]:
    code = (
        "from backend.app.database import get_db_session, Car;"
        "db=get_db_session();"
        "print('cars_in_db', db.query(Car).count());"
        "db.close()"
    )
    return run([python_exe, "-c", code], timeout=60)


def ensure_ollama_model() -> tuple[bool, str]:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "deepseek-r1:14b")
    try:
        resp = requests.get(f"{base}/api/tags", timeout=8)
        resp.raise_for_status()
        names = {m.get("name", "") for m in resp.json().get("models", [])}
        if model in names or any(x.startswith(model.split(":")[0]) for x in names):
            return True, f"Model already available: {model}"
    except Exception as exc:
        return False, f"Ollama not reachable: {exc}"

    ok, out = run(["ollama", "pull", model], timeout=3600)
    return ok, out


def test_nhtsa_retry() -> tuple[bool, str]:
    try:
        from backend.app.agents.nhtsa_api import decode_vin

        result = decode_vin("5FNRL6H79LB123456")
        if result.get("status") == "ok":
            return True, f"Decoded {result.get('year')} {result.get('make')} {result.get('model')}"
        return False, result.get("error", "NHTSA decode failed")
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    python_exe = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    report: list[tuple[str, bool, str]] = []

    missing = check_env()
    report.append(("env_vars", len(missing) == 0, "missing=" + ",".join(missing) if missing else "ok"))

    ok, out = ensure_dependencies(python_exe)
    report.append(("dependencies", ok, out.splitlines()[-1] if out else ""))

    ok, out = ensure_docker_postgres()
    report.append(("docker_postgres", ok, out.splitlines()[-1] if out else ""))

    ok, out = ensure_database_connectivity(python_exe)
    report.append(("database", ok, out))

    ok, out = ensure_ollama_model()
    report.append(("ollama", ok, out))

    ok, out = test_nhtsa_retry()
    report.append(("nhtsa", ok, out))

    print("=" * 72)
    print("IMPERIAL CARS AI - FIX ALL REPORT")
    print("=" * 72)
    failures = 0
    for name, status, details in report:
        marker = "PASS" if status else "FAIL"
        print(f"[{marker}] {name}: {details}")
        if not status:
            failures += 1

    print("-" * 72)
    print(f"Total checks: {len(report)} | Failed: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
