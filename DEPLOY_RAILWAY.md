# Imperial Cars AI Deployment - Railway + One-Week Demo Plan

Project root:
C:\Users\amrit\OneDrive\Documents\AI Data Science Project

## Recommended path for 7-day deadline
For your boss demo, use Local Network Deployment first (same Wi-Fi):
- Fastest setup
- Lowest risk
- Full feature parity
- No cloud model-hosting complexity

Use cloud deployment after demo hardening.

## Track A - Local Network Demo (Primary)
1. Build frontend:
```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
.\scripts\build_frontend.ps1
```
2. Start backend for LAN:
```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
3. Open tablet URL:
```text
http://<YOUR_LAPTOP_IP>:8000
```
4. Confirm API health:
```text
http://<YOUR_LAPTOP_IP>:8000/api/health
```

If this works, your demo is ready.

## Track B - Railway Cloud Deployment (Optional)

### 1) Push project to GitHub
```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
git init
git add .
git commit -m "Initial Imperial Cars AI deployment baseline"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

### 2) Create Railway project
1. Go to Railway and sign in.
2. New Project -> Deploy from GitHub repo.
3. Select your Imperial Cars AI repository.
4. Railway will build using Dockerfile / service settings.

### 3) Configure environment variables in Railway
Set at minimum:
- DATABASE_URL
- APP_ENV=production
- LOG_LEVEL=INFO
- CORS_ORIGINS=<your frontend URL>
- OLLAMA_BASE_URL
- OLLAMA_MODEL
- SERVICE_VIDEO_APPROVAL_SECRET
- SALESPERSON_PIN_HASH

Optional if used:
- TWILIO_ACCOUNT_SID
- TWILIO_AUTH_TOKEN
- TWILIO_PHONE_NUMBER
- SMTP_SERVER
- SMTP_PORT
- SMTP_USER
- SMTP_PASSWORD

### 4) Ollama strategy options (important)

Option 1 (quick, not ideal): use laptop Ollama as remote backend dependency
- Keep Ollama running on laptop.
- Expose laptop Ollama (for example via ngrok TCP/HTTP tunnel).
- Set Railway OLLAMA_BASE_URL to exposed endpoint.
- Laptop must stay online.

Option 2 (recommended long-term): host model service remotely
- Deploy Ollama/model server on cloud VM or container.
- Point Railway backend to that stable endpoint.
- Better reliability for real customer use.

### 5) Validate cloud deployment
After deploy:
1. Open Railway app URL.
2. Check `/api/health`.
3. Test chatbot query and payment estimator.
4. Verify static app routes load directly.

## Practical recommendation
- Demo this week: Track A (local network) for stability.
- Production after demo: Railway + remote model service.
