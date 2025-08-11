// Electron main process entry for erudi (Windows-focused)
// Responsibilities:
// - Create the BrowserWindow (renderer)
// - Spawn the backend (dev: python run.py, packaged: backend.exe)
// - Stream & parse backend stdout/stderr for JSON events
// - Forward events/logs to renderer via IPC channels
// - Provide restart + directory dialog IPC APIs

const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require('fs');

// Process / backend state holders
let backendProc = null;        // Child process handle
let mainWindow = null;         // BrowserWindow reference
let backendReady = false;      // Set after 'ready' JSON event
let lastReadyPayload = null;   // Store last ready payload for renderer reload
let startupError = false;      // Set after any 'startup_error' JSON event
let watchdogTimer = null;      // Timeout guard for backend readiness
let stdoutBuffer = "";        // Line assembly buffer for stdout
let stderrBuffer = "";        // Line assembly buffer for stderr

// Safe IPC send helper (avoids errors if window destroyed)
function safeSend(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(channel, payload);
}

// Handle one complete backend output line
// - Always forward as raw log (backend-log / backend-log-error)
// - If JSON parse succeeds and contains an 'event' key, forward structured 'backend-event'
// - Update internal flags on ready / startup_error to stop watchdog
function handleBackendLine(line, isError = false) {
  if (!line || !line.trim()) return;           // Ignore empty lines
  safeSend(isError ? "backend-log-error" : "backend-log", line);
  
  // Check for specific error patterns in stderr logs
  if (isError && line) {
    let errorCode = null;
    let errorMessage = line;

    // CUDA-related errors
    if (line.includes('NVML library not found') || line.includes('could not be found')) {
      errorCode = 'GPU_DRIVER_MISSING';
    } else if (line.includes('CUDA version') && line.includes('mismatch')) {
      errorCode = 'CUDA_VERSION_MISMATCH';
    } else if (line.includes('CUDA') && (line.includes('not found') || line.includes('not available'))) {
      errorCode = 'CUDA_NOT_FOUND';
    } else if (line.includes('No module named')) {
      if (line.includes('torch') || line.includes('pynvml') || line.includes('bitsandbytes')) {
        errorCode = 'MISSING_DEPENDENCY';
      }
    } else if (line.includes('ImportError') || line.includes('import error')) {
      errorCode = 'IMPORT_ERROR';
    } else if (line.includes('No NVIDIA GPU') || line.includes('No CUDA device')) {
      errorCode = 'NO_NVIDIA_GPU';
    } else if (line.includes('GPU initialization failed') || line.includes('nvmlInit')) {
      errorCode = 'GPU_INIT_FAILED';
    }

    // If we detected a specific error, send it as a structured event
    if (errorCode) {
      safeSend("backend-event", { 
        event: "startup_error", 
        code: errorCode, 
        message: errorMessage 
      });
      startupError = true;
      clearWatchdog();
      return;
    }
  }

  try {
    const obj = JSON.parse(line);
    if (obj && obj.event) {
      safeSend("backend-event", obj);
      if (obj.event === "ready") { backendReady = true; lastReadyPayload = obj; clearWatchdog(); }
      else if (obj.event === "startup_error") { startupError = true; clearWatchdog(); }
    }
  } catch (_) { /* Non-JSON line: ignore for events */ }
}

// Cancel watchdog timer if active
function clearWatchdog() { if (watchdogTimer) { clearTimeout(watchdogTimer); watchdogTimer = null; } }

// Start watchdog: if backend neither ready nor errored within 35s, emit synthetic startup_error
function startWatchdog() {
  clearWatchdog();
  watchdogTimer = setTimeout(() => {
    if (!backendReady && !startupError) {
      safeSend("backend-event", { event: "startup_error", code: "STARTUP_TIMEOUT", message: "Backend did not signal readiness" });
    }
  }, 35000);
}

// Launch or relaunch backend process
// Dev mode assumptions:
//   - Project root is two levels above this file (../..)
//   - Python venv at backend/venv/Scripts/python.exe
//   - run.py at project root
// Packaged mode assumptions:
//   - backend executable at resources/backend/backend.exe
function spawnBackend() {
  // Kill previous backend if still alive
  if (backendProc && !backendProc.killed) { try { backendProc.kill(); } catch(_) {} }
  // Reset state + buffers
  backendReady = false; startupError = false; stdoutBuffer = ""; stderrBuffer = "";

  let backendCmd;        // Executable path
  let backendArgs = [];  // Arguments (only run.py in dev)
  let backendCwd;        // Working directory
  let mode;              // 'dev' or 'packaged'

  if (app.isPackaged) {
    mode = 'packaged';
    const backendExe = path.join(process.resourcesPath, 'backend', 'backend.exe');
    backendCmd = backendExe;
    backendCwd = path.dirname(backendExe);
  } else {
    mode = 'dev';
    const projectRoot = path.resolve(process.cwd(), '..');
    const runPy = path.join(projectRoot, 'run.py');
    const pythonExe = path.join(projectRoot, 'backend', 'venv', 'Scripts', 'python.exe');
    backendCmd = pythonExe;
    backendArgs = [runPy];
    backendCwd = projectRoot;
    // Basic dev environment sanity check
    if (!fs.existsSync(pythonExe) || !fs.existsSync(runPy)) {
      safeSend('backend-event', { event: 'startup_error', code: 'DEV_SETUP_MISSING', message: 'python.exe or run.py not found (expected backend/venv + run.py)' });
      return;
    }
  }

  // Spawn the backend child process (capture stdout/stderr for events/logs)
  backendProc = spawn(backendCmd, backendArgs, {
    cwd: backendCwd,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe']
  });

  // Inform renderer that launcher has spawned (useful for debugging sequence)
  safeSend("backend-event", { event: "launcher_spawned", mode });
  startWatchdog();

  // Process-level error (spawn failure, permission, missing exe)
  backendProc.on('error', err => {
    safeSend("backend-event", { event: "startup_error", code: "SPAWN_FAIL", message: String(err), mode });
  });

  // Exit event (normal or crash). If exit before ready & no explicit startup_error, synthesize EXIT_BEFORE_READY.
  backendProc.on('exit', code => {
    safeSend("backend-event", { event: "backend_exit", code, mode });
    if (!backendReady && !startupError) {
      safeSend("backend-event", { event: "startup_error", code: "EXIT_BEFORE_READY", message: `Backend exited early (${code})`, mode });
    }
  });

  // Accumulate stdout chunks into complete lines
  backendProc.stdout.on('data', chunk => {
    stdoutBuffer += chunk.toString();
    const lines = stdoutBuffer.split(/\r?\n/); stdoutBuffer = lines.pop();
    lines.forEach(l => handleBackendLine(l, false));
  });

  // Accumulate stderr chunks into complete lines
  backendProc.stderr.on('data', chunk => {
    stderrBuffer += chunk.toString();
    const lines = stderrBuffer.split(/\r?\n/); stderrBuffer = lines.pop();
    lines.forEach(l => handleBackendLine(l, true));
  });
}

// Create the main application window & wire IPC handlers
async function createWindow() {
    // Robust preload and startUrl fallback
    mainWindow = new BrowserWindow({
      width: 1280,
      height: 800,
      autoHideMenuBar: true,
      webPreferences: {
        preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
        contextIsolation: true,
        nodeIntegration: false,
        webSecurity: false
      },
    });

    // Modifier les en-têtes CSP pour permettre les appels API vers localhost:8000
    mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
      const csp = [
        "default-src 'self' 'unsafe-inline' data: blob:",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
        // allow your local API + Apps Script endpoints + websockets
        "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws: wss: https://script.google.com https://script.googleusercontent.com",
        // allow images (incl. data URLs) + https (for any icons on your help page)
        "img-src 'self' data: blob: https:",
        // allow Google Fonts CSS
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        // allow Google Fonts files
        "font-src 'self' data: https://fonts.gstatic.com",
        // (optional) if anything is iframed from Google
        "frame-src https://docs.google.com https://script.google.com"
      ].join('; ');

      callback({
        responseHeaders: {
          ...details.responseHeaders,
          "Content-Security-Policy": [csp],
        }
      });
    });

    await mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY); // Load renderer (React bundle)
    spawnBackend(); // Start backend after renderer ready so no events are missed

  // Quand le renderer se (re)charge, lui renvoyer l'état courant
  mainWindow.webContents.on('did-finish-load', () => {
    if (backendReady) {
      safeSend("backend-event", lastReadyPayload || { event: "ready" });
    }
  });

  // IPC: directory selection dialog
  ipcMain.handle('dialog:openDirectory', async () => {
    const { filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory'] });
    return filePaths[0];
  });

  // IPC: restart backend (used by LoadingScreen retry)
  ipcMain.handle('backend:restart', async () => { spawnBackend(); return true; });

  // IPC: get backend status (for renderer reload)
  ipcMain.handle('backend:getStatus', () => ({ backendReady, lastReadyPayload }));
}

// App lifecycle hooks
app.whenReady().then(createWindow);
app.on('window-all-closed', () => { app.quit(); });
app.on('before-quit', () => { if (backendProc) backendProc.kill(); });
