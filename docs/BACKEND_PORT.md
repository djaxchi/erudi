# Backend Port Configuration

## Overview

Erudi's backend can run on any port between **8765-8864** (default: 8765). The frontend automatically adapts to the port using environment variables.

## How It Works

### 1. Backend (Python)
The backend's default port is configured in `backend/run.py`:
```python
parser.add_argument("--port", type=int, default=8765, ...)
```

You can override it when starting:
```bash
python backend/run.py --port 8000
```

### 2. Frontend (Electron)
The frontend reads the port from the `BACKEND_PORT` environment variable:
- **Production mode**: Spawns backend and captures actual port from backend JSON events
- **Dev mode**: Reads `BACKEND_PORT` from environment (defaults to 8765)

## Configuration Methods

### Method 1: Environment Variable (Recommended)
Set `BACKEND_PORT` in your `.env` file:
```bash
BACKEND_PORT=8765  # or any port you choose
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

1. **Backend**: `backend/run.py` - Default port: 8765
2. **Frontend Config**: `frontend/src/config/api.js` - Reads `BACKEND_PORT`
3. **Frontend Main**: `frontend/src/main.js` - Dev mode health check
4. **Environment**: `.env` - Configuration file

## Troubleshooting

### Port Mismatch Error
```
GET http://127.0.0.1:8765/erudi/health/ net::ERR_CONNECTION_REFUSED
```

**Solution**: Ensure `BACKEND_PORT` matches the port backend is running on:
1. Check backend startup logs for actual port
2. Set `BACKEND_PORT` in `.env` file
3. Restart frontend

### Testing
```bash
# Check backend is running
curl http://127.0.0.1:8765/erudi/health/

# Or with custom port
curl http://127.0.0.1:8000/erudi/health/
```

Expected response:
```json
{"status":"ok","message":"Backend is running"}
```
