import os
import json
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv(".env.local", override=True)
load_dotenv(".env", override=False)


def _split_csv(value: str, default: str) -> List[str]:
	raw = (value or default).strip()
	return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_trusted_hosts(value: str, default: str) -> List[str]:
	raw = (value or default).strip()

	# Support JSON array style, e.g. ["localhost", "127.0.0.1"]
	if raw.startswith("[") and raw.endswith("]"):
		try:
			parsed = json.loads(raw)
			if isinstance(parsed, list):
				hosts = [str(item).strip() for item in parsed if str(item).strip()]
				if hosts:
					return hosts
		except json.JSONDecodeError:
			pass

	# Support a single wildcard host value.
	if raw == "*":
		return ["*"]

	return [
		item.strip().strip('"').strip("'")
		for item in raw.split(",")
		if item.strip().strip('"').strip("'")
	]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "")
DATA_DIR = os.getenv("DATA_DIR", "data")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))

APP_NAME = os.getenv("APP_NAME", "Imperial Cars AI API")
APP_VERSION = os.getenv("APP_VERSION", "1.1.0")
APP_ENV = os.getenv("APP_ENV", "development").lower()

CORS_ORIGINS = _split_csv(
	os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8501"),
	"http://localhost:3000,http://localhost:8501",
)

TRUSTED_HOSTS = _parse_trusted_hosts(
	os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1,.imperialcars.local"),
	"localhost,127.0.0.1,.imperialcars.local",
)

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_JSON = os.getenv("LOG_JSON", "1").strip().lower() not in {"0", "false", "no"}
INVENTORY_STALE_HOURS = int(os.getenv("INVENTORY_STALE_HOURS", "168"))
BREAK_EVEN_MONTH = int(os.getenv("BREAK_EVEN_MONTH", "48"))
SERVICE_VIDEO_APPROVAL_SECRET = os.getenv("SERVICE_VIDEO_APPROVAL_SECRET", "")
ADMIN_API_SECRET = os.getenv("ADMIN_API_SECRET", "")
MODEL_NAME = os.getenv("MODEL_NAME", os.getenv("OLLAMA_MODEL", os.getenv("SALES_BASE_MODEL", "llama3")))
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", os.path.join(os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base"), "index"))
NHTSA_API_ENABLED = os.getenv("NHTSA_API_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
FUELECONOMY_API_ENABLED = os.getenv("FUELECONOMY_API_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
CARFAX_API_KEY = os.getenv("CARFAX_API_KEY", "")
KBB_API_KEY = os.getenv("KBB_API_KEY", "")
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
EXTERNAL_API_TIMEOUT_SECONDS = float(os.getenv("EXTERNAL_API_TIMEOUT_SECONDS", "5"))
