#!/usr/bin/env bash
set -euo pipefail

# One-click setup and launch for Imperial Cars AI on Linux/macOS.

PROJECT_PATH="/c/Users/amrit/OneDrive/Documents/AI Data Science Project"
if [[ "$(uname -s)" == "Linux" ]]; then
  PROJECT_PATH="/mnt/c/Users/amrit/OneDrive/Documents/AI Data Science Project"
fi
if [[ "$(uname -s)" == "Darwin" ]]; then
  PROJECT_PATH="/Users/amrit/OneDrive/Documents/AI Data Science Project"
fi

if [[ -d "$PWD" && -f "$PWD/requirements.txt" && -d "$PWD/backend" ]]; then
  PROJECT_PATH="$PWD"
fi

VENV_PATH="$PROJECT_PATH/.venv"
VENV_PY="$VENV_PATH/bin/python"
ENV_FILE="$PROJECT_PATH/.env"
ENV_EXAMPLE="$PROJECT_PATH/.env.example"
DATABASE_URL="postgresql://imperial_admin:Imperial123!@localhost:55433/imperial_dealership"
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="deepseek-r1:14b"

step() {
  echo
  echo "=== $1 ==="
}

fail() {
  echo "ERROR: $1" >&2
  exit 1
}

ensure_cmd() {
  local cmd="$1"
  local hint="$2"
  local optional="${3:-false}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    if [[ "$optional" == "true" ]]; then
      echo "Optional dependency missing: $cmd"
      echo "Hint: $hint"
      return 0
    fi
    fail "Missing dependency '$cmd'. $hint"
  fi
}

upsert_env() {
  local file="$1"
  local key="$2"
  local value="$3"

  touch "$file"
  if grep -qE "^[[:space:]]*$key=" "$file"; then
    sed -i.bak "s|^[[:space:]]*$key=.*|$key=$value|" "$file"
    rm -f "$file.bak"
  else
    echo "$key=$value" >> "$file"
  fi
}

retry() {
  local retries="$1"
  local delay="$2"
  shift 2

  local attempt=1
  while (( attempt <= retries )); do
    if "$@"; then
      return 0
    fi
    if (( attempt == retries )); then
      return 1
    fi
    echo "Command failed (attempt $attempt/$retries). Retrying in ${delay}s..."
    sleep "$delay"
    ((attempt++))
  done
}

step "Step 0: Telegram Bot Token"
read -r -s -p "Enter Telegram bot token from BotFather: " TELEGRAM_BOT_TOKEN
echo
[[ -z "$TELEGRAM_BOT_TOKEN" ]] && fail "Telegram bot token cannot be empty."

step "Step 1: Check prerequisites"
[[ -d "$PROJECT_PATH" ]] || fail "Project path not found: $PROJECT_PATH"

ensure_cmd python3 "Install Python 3.10+ from https://www.python.org/downloads/"
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=${PY_VER%%.*}
PY_MINOR=${PY_VER##*.}
if (( PY_MAJOR < 3 || (PY_MAJOR == 3 && PY_MINOR < 10) )); then
  fail "Python 3.10+ required. Detected: $PY_VER"
fi
echo "Python version OK: $PY_VER"

ensure_cmd docker "Install Docker Desktop/Engine: https://docs.docker.com/get-docker/"
if docker compose version >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DOCKER_COMPOSE=(docker-compose)
else
  fail "Docker Compose missing. Install Docker Compose plugin or docker-compose binary."
fi

ensure_cmd git "Install Git: https://git-scm.com/downloads" true

if ! command -v tesseract >/dev/null 2>&1; then
  case "$(uname -s)" in
    Darwin)
      ensure_cmd brew "Install Homebrew first: https://brew.sh"
      brew install tesseract
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y tesseract-ocr
      else
        fail "tesseract missing and apt-get not found. Install Tesseract via your distro package manager."
      fi
      ;;
    *)
      fail "Unsupported OS for auto-installing tesseract."
      ;;
  esac
fi

echo "Tesseract available: $(command -v tesseract)"

step "Step 2: Create/Activate virtual environment"
cd "$PROJECT_PATH"
if [[ ! -x "$VENV_PY" ]]; then
  python3 -m venv "$VENV_PATH"
fi
[[ -x "$VENV_PY" ]] || fail "Virtual environment creation failed."
source "$VENV_PATH/bin/activate"

step "Step 3: Install Python dependencies"
"$VENV_PY" -m pip install --upgrade pip setuptools wheel
"$VENV_PY" -m pip install -r "$PROJECT_PATH/requirements.txt"
"$VENV_PY" -m pip install kaleido pypdf whisper transformers torch psycopg2-binary sqlalchemy pgvector reportlab apscheduler plotly pytesseract opencv-python python-dotenv requests

step "Step 4: Configure environment variables"
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
  else
    touch "$ENV_FILE"
  fi
fi

upsert_env "$ENV_FILE" "TELEGRAM_BOT_TOKEN" "$TELEGRAM_BOT_TOKEN"
upsert_env "$ENV_FILE" "DATABASE_URL" "$DATABASE_URL"
upsert_env "$ENV_FILE" "OLLAMA_BASE_URL" "$OLLAMA_BASE_URL"
upsert_env "$ENV_FILE" "OLLAMA_MODEL" "$OLLAMA_MODEL"

step "Step 5: Start Docker services"
"${DOCKER_COMPOSE[@]}" up -d

POSTGRES_ID=$(docker compose ps -q postgres 2>/dev/null || true)
if [[ -z "$POSTGRES_ID" ]]; then
  POSTGRES_ID=$(docker ps --filter "name=postgres" --format "{{.ID}}" | head -n1 || true)
fi
[[ -n "$POSTGRES_ID" ]] || fail "Could not find running postgres container."

healthy=false
for i in $(seq 1 30); do
  if docker exec "$POSTGRES_ID" pg_isready -U imperial_admin -d imperial_dealership >/dev/null 2>&1; then
    healthy=true
    break
  fi
  echo "Waiting for PostgreSQL... ($i/30)"
  sleep 2
done
[[ "$healthy" == "true" ]] || fail "PostgreSQL did not become healthy in time."

step "Step 6: Initialize database"
export DATABASE_URL
export OLLAMA_BASE_URL
export OLLAMA_MODEL
export TELEGRAM_BOT_TOKEN

retry 5 4 "$VENV_PY" "$PROJECT_PATH/scripts/init_db.py" || fail "init_db.py failed after retries"

DATASET_PATH="$PROJECT_PATH/data/raw/large_cars_dataset.csv"
if [[ ! -f "$DATASET_PATH" ]]; then
  echo "Dataset not found at $DATASET_PATH. Importer will generate sample data automatically."
fi

retry 5 4 "$VENV_PY" "$PROJECT_PATH/scripts/import_car_data.py" || fail "import_car_data.py failed after retries"

step "Step 7: Verify Ollama model"
if ! command -v ollama >/dev/null 2>&1; then
  fail "Ollama not installed. Install from https://ollama.com/download"
fi

if ! ollama list | grep -q "$OLLAMA_MODEL"; then
  ollama pull "$OLLAMA_MODEL"
else
  echo "Ollama model already available: $OLLAMA_MODEL"
fi

step "Step 8: OCR test"
cat > "$PROJECT_PATH/scripts/test_ocr.py" <<'PY'
import os
import sys
import cv2
import numpy as np
import pytesseract

img = np.full((140, 480, 3), 255, dtype=np.uint8)
cv2.putText(img, "OCR works", (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 0), 3)
text = pytesseract.image_to_string(img)

if "OCR" in text.upper() and "WORK" in text.upper():
    print("OCR works")
    sys.exit(0)

print("OCR check failed. Extracted:", repr(text))
sys.exit(1)
PY

if "$VENV_PY" "$PROJECT_PATH/scripts/test_ocr.py"; then
  echo "OCR validation passed."
else
  echo "WARNING: OCR validation failed. Ensure tesseract is correctly installed and in PATH."
fi

step "Step 9: Launch services in background"
mkdir -p "$PROJECT_PATH/logs"

if ! pgrep -f "streamlit run frontend/app.py" >/dev/null 2>&1; then
  nohup "$VENV_PY" -m streamlit run "$PROJECT_PATH/frontend/app.py" --server.port 8501 > "$PROJECT_PATH/logs/streamlit.log" 2>&1 &
fi

if ! pgrep -f "sales_bot.py" >/dev/null 2>&1; then
  nohup "$VENV_PY" "$PROJECT_PATH/sales_bot.py" > "$PROJECT_PATH/logs/telegram_bot.log" 2>&1 &
fi

if ! pgrep -f "uvicorn backend.app.main:app" >/dev/null 2>&1; then
  nohup "$VENV_PY" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > "$PROJECT_PATH/logs/api.log" 2>&1 &
fi

step "Step 10: Success"
echo "Imperial Cars AI setup completed successfully."
echo "Streamlit: http://localhost:8501"
echo "API docs:  http://localhost:8000/docs"
echo "pgAdmin:   http://localhost:5051"
echo
echo "Sample bot commands:"
echo "  /ask What SUV under 30000 do you recommend?"
echo "  /specs Toyota Camry 2024"
echo "  /compare Honda Civic vs Toyota Corolla"
echo "  /payment 30000 5000 6.9 60"
echo
echo "OCR is configured and tesseract is expected in PATH."
echo "If Docker commands fail, rerun with sudo (or ensure your user is in the docker group)."
