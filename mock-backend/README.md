# Mock Backend for Erudi - Replacement Tutorial

This is a **temporary** standalone Python FastAPI backend that provides mock responses for all Erudi API endpoints. This mock backend is designed to be replaced with the real backend once it's built.

## 🚨 Important: This is a Mock Backend

This backend provides **fake responses** for development and testing purposes only. It does not contain real AI functionality, model training, or data persistence. Replace it with the real backend for production use.

## Quick Start (Current Mock Backend)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python server.py [port]
```

Default port is 8001 if no port is specified.

## 🔄 How to Replace with Real Backend

When your real backend is ready, follow these steps to integrate it with the Electron frontend:

### Step 1: Prepare Your Real Backend

Ensure your real backend:
- ✅ Runs on the same port (8000) or update the port configuration
- ✅ Implements all the required API endpoints (see endpoint list below)
- ✅ Supports the same request/response formats
- ✅ Has a `/health` endpoint that returns `{"status": "ok", "message": "...", "timestamp": "..."}`
- ✅ Is packaged as a standalone executable or has clear startup instructions

### Step 2: Update Electron Configuration

#### Option A: Replace Python Script (Recommended)
1. Replace `mock-backend/server.py` with your real backend's startup script
2. Update `mock-backend/requirements.txt` with your backend's dependencies
3. If your backend is not Python, update the startup command in `frontend/src/main.js`

#### Option B: Update Forge Configuration
1. In `frontend/forge.config.js`, update the `extraResource` section:
```javascript
extraResource: [
  "../your-real-backend-directory"  // Replace "../mock-backend"
]
```

2. Update the backend path in `frontend/src/main.js`:
```javascript
// In the startMockBackend function, update these lines:
if (app.isPackaged) {
  backendPath = path.join(process.resourcesPath, 'your-real-backend-directory', 'your-startup-script');
} else {
  backendPath = path.join(__dirname, '..', '..', '..', 'your-real-backend-directory', 'your-startup-script');
}
```

### Step 3: Update Startup Command

In `frontend/src/main.js`, find the `startMockBackend` function and update the spawn command:

```javascript
// For Python backend (current):
const pythonPath = '/opt/anaconda3/bin/python3';
mockBackendProcess = spawn(pythonPath, [backendPath, PORT.toString()], {
  stdio: ['pipe', 'pipe', 'pipe'],
  cwd: workingDir
});

// For other backends, update accordingly:
// Example for Node.js backend:
mockBackendProcess = spawn('node', [backendPath, PORT.toString()], {
  stdio: ['pipe', 'pipe', 'pipe'],
  cwd: workingDir
});

// Example for compiled binary:
mockBackendProcess = spawn(backendPath, [PORT.toString()], {
  stdio: ['pipe', 'pipe', 'pipe'],
  cwd: workingDir
});
```

### Step 4: Test the Integration

1. Test in development mode:
```bash
cd frontend
npm start
```

2. Test the packaged version:
```bash
cd frontend
npm run package
open out/erudi-darwin-arm64/erudi.app
```

3. Verify the health endpoint responds correctly:
```bash
curl http://127.0.0.1:8000/health
```

### Step 5: Update API Configurations (If Needed)

If your real backend uses different:
- **Port**: Update `PORT` constant in `frontend/src/main.js`
- **Base URL**: Update the `API` constant in `frontend/src/services/*.js` files
- **Endpoints**: Update endpoint paths in service files to match your backend's API structure

## 📋 Required API Endpoints

Your real backend must implement these endpoints for full compatibility:

### Core Endpoints
- `GET /health` - Health check
- `GET /main_window/health` - Alternative health check
- `GET /main_window/welcome-popup` - Welcome popup configuration

### LLM Management
- `GET /main_window/llms` - Get available LLMs
- `GET /main_window/llms/local` - Get local LLMs
- `GET /main_window/llms/remote` - Get remote LLMs

### Conversation Management
- `POST /conversations` - Create conversation
- `GET /conversations` - List conversations
- `GET /conversations/{id}` - Get conversation
- `PUT /conversations/{id}` - Update conversation
- `DELETE /conversations/{id}` - Delete conversation
- `POST /conversations/bulk-delete` - Bulk delete conversations
- `POST /conversations/{id}/query` - Send message to conversation
- `POST /conversations/{id}/generate-title` - Generate conversation title
- `POST /conversations/{id}/store_error_message` - Store error message

### Message Management
- `GET /conversations/{id}/messages` - Get conversation messages
- `POST /messages/{id}/star` - Star/unstar message

### Arena (Multi-model comparison)
- `POST /arena/{llm_id}/query` - Query specific model in arena

### Hardware Information
- `GET /hardware/app_startup` - Get hardware info for app startup

### Training (Placeholders)
- `GET /main_window/train-new-model` - Training availability

## 🔧 Frontend Service Files to Review

When replacing the backend, you may need to update these frontend files:
- `frontend/src/services/conversationService.js`
- `frontend/src/services/arenaService.js`

## 🐛 Troubleshooting

### Backend Not Starting
1. Check the log file: `/tmp/erudi-backend.log` (on macOS: `/var/folders/.../erudi-backend.log`)
2. Verify the backend executable has proper permissions
3. Ensure all dependencies are installed
4. Check if the port is already in use

### API Connection Issues
1. Verify the backend is running on the expected port
2. Check CORS configuration in your backend
3. Ensure all required endpoints are implemented
4. Test endpoints manually with `curl` or Postman

### Packaging Issues
1. Ensure your backend files are included in the `extraResource` configuration
2. Check that relative paths are correctly resolved in packaged mode
3. Verify your backend can run in the packaged environment

## ✅ Migration Checklist

- [ ] Real backend implements all required endpoints
- [ ] Health endpoint returns expected format
- [ ] Backend starts successfully on port 8000
- [ ] Updated `forge.config.js` extraResource path
- [ ] Updated backend path in `main.js`
- [ ] Updated startup command in `main.js`
- [ ] Tested in development mode (`npm start`)
- [ ] Tested packaged version (`npm run package`)
- [ ] All API calls work correctly
- [ ] Backend shuts down gracefully with the app

## 📝 Notes

- The current mock backend provides realistic but fake responses
- Streaming endpoints simulate real streaming behavior
- In-memory storage means data is lost on restart
- Replace this entire directory structure with your real backend when ready