# Local Network Setup (Laptop -> Tablet)

Project root:
C:\Users\amrit\OneDrive\Documents\AI Data Science Project

## Goal
Run backend + frontend on one port (8000) and access from Android tablet on same Wi-Fi.

## 1) Find laptop IP address
Open PowerShell:
```powershell
ipconfig
```
Use the IPv4 address from your active Wi-Fi adapter (example: 10.20.0.91).

## 2) Build frontend production files
```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
.\scripts\build_frontend.ps1
```
This creates:
- C:\Users\amrit\OneDrive\Documents\AI Data Science Project\frontend-react\dist

## 3) Start FastAPI on all interfaces
```powershell
cd "C:\Users\amrit\OneDrive\Documents\AI Data Science Project"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## 4) Allow firewall access to port 8000
If Windows prompts, allow Private network access.

If needed, add manual firewall rule (run as admin):
```powershell
New-NetFirewallRule -DisplayName "ImperialCarsAI-8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

## 5) Open from Android tablet
On tablet Chrome:
```text
http://<LAPTOP_IP>:8000
```
Example:
```text
http://10.20.0.91:8000
```

Health check URL:
```text
http://<LAPTOP_IP>:8000/api/health
```

## 6) Demo checklist
- Dashboard loads on tablet.
- Chatbot responds.
- Inventory displays.
- Payment estimator works.
- Paperwork/OCR upload works.

## Troubleshooting
- Tablet cannot connect:
  - Confirm both devices are on same Wi-Fi.
  - Confirm backend is running and listening on 0.0.0.0:8000.
  - Confirm firewall rule allows inbound TCP 8000.
- API works but UI is blank:
  - Re-run frontend build script.
  - Confirm dist folder exists.
- Chatbot fails:
  - Ensure Ollama is running locally.
  - Check OLLAMA_BASE_URL in .env.
