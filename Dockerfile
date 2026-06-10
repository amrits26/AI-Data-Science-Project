# Stage 1: build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend-react/package*.json ./
RUN npm install
COPY frontend-react/ ./
RUN npm run build

# Stage 2: backend runtime
FROM python:3.11-slim AS backend-runtime
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY scripts ./scripts
COPY sales_bot.py ./sales_bot.py
COPY data ./data
COPY --from=frontend-builder /frontend/dist ./frontend_dist

EXPOSE 8000
CMD ["gunicorn", "--workers", "3", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "backend.app.main:app"]
