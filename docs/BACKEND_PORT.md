# Backend Port Configuration

## Overview

Erudi's canonical port is **27182** — the leading digits of Euler's number _e_ (2.7182…),
a wink for an app built for erudites. It's also a practically safe default on every OS:
IANA-unassigned, below every OS's ephemeral range (Linux 32768+, Windows/macOS 49152+, plus
Windows Hyper-V/WSL exclusions), and clear of the crowded dev/LLM defaults (Ollama 11434,
LM Studio 1234, vLLM 8000, llama.cpp/Tomcat 8080).

The backend prefers 27182 and scans **27182–27199** if it's taken, then announces the
resolved port via its JSON lifecycle events; the frontend consumes that announced port, so
it always targets the right one. (Erudi's inference servers own the rest of the block:
llama.cpp 27200–27299, MLX 27300–27399.)

## How It Works

### 1. Backend (Python)
The backend's default port is configured in `backend/run.py`:
```python
parser.add_argument("--port", type=int, default=27182, ...)
```

You can override it when starting:
```bash
python backend/run.py --port 8000
```

### 2. Frontend (Electron)
The frontend reads the port from the `BACKEND_PORT` environment variable:
- **Production mode**: Spawns backend and captures actual port from backend JSON events
- **Dev mode**: Reads `BACKEND_PORT` from environment (defaults to 27182)

## Configuration Methods

### Method 1: Environment Variable (Recommended)
Set `BACKEND_PORT` in your `.env` file:
```bash
BACKEND_PORT=27182  # or any port you choose
```

### Method 2: Command Line
```bash
# Backend
cd backend
.venv/bin/python run.py --port 8000

# Frontend (in another terminal)
BACKEND_PORT=8000 npm start
```

### Method 3: System Environment
```bash
export BACKEND_PORT=8000
npm start
```

## Cross-Platform Usage

### macOS/Linux
```bash
# Set port for current session
export BACKEND_PORT=8000

# Start backend
cd backend && .venv/bin/python run.py --port 8000

# Start frontend (in another terminal)
cd frontend && npm start
```

### Windows (CMD)
```cmd
set BACKEND_PORT=8000
npm start
```

### Windows (PowerShell)
```powershell
$env:BACKEND_PORT="8000"
npm start
```

## Files Involved

1. **Backend**: `backend/run.py` - Default port: 27182
2. **Frontend Config**: `frontend/src/config/api.js` - Reads `BACKEND_PORT`
3. **Frontend Main**: `frontend/src/main.js` - Dev mode health check
4. **Environment**: `.env` - Configuration file

## Troubleshooting

### Port Mismatch Error
```
GET http://127.0.0.1:27182/erudi/health/ net::ERR_CONNECTION_REFUSED
```

**Solution**: Ensure `BACKEND_PORT` matches the port backend is running on:
1. Check backend startup logs for actual port
2. Set `BACKEND_PORT` in `.env` file
3. Restart frontend

### Testing
```bash
# Check backend is running
curl http://127.0.0.1:27182/erudi/health/

# Or with custom port
curl http://127.0.0.1:8000/erudi/health/
```

Expected response:
```json
{"status":"ok","message":"Backend is running"}
```
