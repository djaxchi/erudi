const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require('fs');

let backendProc = null;       
let mainWindow = null;        
let backendReady = false;     
let lastReadyPayload = null;  
let startupError = false;     
let watchdogTimer = null;     
let stdoutBuffer = "";       
let stderrBuffer = "";       

function safeSend(channel, payload) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(channel, payload);
}

function handleBackendLine(line, isError = false) {
  if (!line || !line.trim()) return;           
  safeSend(isError ? "backend-log-error" : "backend-log", line);
  
  if (isError && line) {
    let errorCode = null;
    let errorMessage = line;

    if (line.includes('NVML library not found') || line.includes('could not be found')) {
      errorCode = 'GPU_DRIVER_MISSING';
    } else if (line.includes('CUDA version') && line.includes('mismatch')) {
      errorCode = 'CUDA_VERSION_MISMATCH';
    } else if (line.includes('CUDA') && (line.includes('not found') || line.includes('not available'))) {
      errorCode = 'CUDA_NOT_FOUND';
    } else if (line.includes('No module named')) {
      if (line.includes('pynvml')) {
        errorCode = 'PYNVML_MISSING';
      } else if (line.includes('torch')) {
        errorCode = 'PYTORCH_MISSING';
      } else if (line.includes('bitsandbytes')) {
        errorCode = 'BITSANDBYTES_MISSING';
      } else if (line.includes('transformers')) {
        errorCode = 'TRANSFORMERS_MISSING';
      } else {
        errorCode = 'MISSING_DEPENDENCY';
      }
    } else if (line.includes('ImportError') || line.includes('import error')) {
      errorCode = 'IMPORT_ERROR';
    } else if (line.includes('No NVIDIA GPU') || line.includes('No CUDA device')) {
      errorCode = 'NO_NVIDIA_GPU';
    } else if (line.includes('GPU initialization failed') || line.includes('nvmlInit')) {
      errorCode = 'GPU_INIT_FAILED';
    }

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
  } catch (_) { }
}

function clearWatchdog() { if (watchdogTimer) { clearTimeout(watchdogTimer); watchdogTimer = null; } }

function startWatchdog() {
  clearWatchdog();
  watchdogTimer = setTimeout(() => {
    if (!backendReady && !startupError) {
      safeSend("backend-event", { event: "startup_error", code: "STARTUP_TIMEOUT", message: "Backend did not signal readiness" });
    }
  }, 120000);
}

function spawnBackend() {
  // Kill previous backend if still alive
  if (backendProc && !backendProc.killed) { try { backendProc.kill(); } catch(_) {} }
  // Reset state + buffers
  backendReady = false; startupError = false; stdoutBuffer = ""; stderrBuffer = "";

  let backendCmd;        
  let backendArgs = [];  
  let backendCwd;        
  let mode;              

  if (app.isPackaged) {
    mode = 'packaged';
    const backendExe = path.join(process.resourcesPath, 'backend', 'backend.exe');
    backendCmd = backendExe;
    backendCwd = path.dirname(backendExe);
  } else {
    mode = 'dev';
    const projectRoot = path.resolve(process.cwd(), '..');
    const runPy = path.join(projectRoot, 'run.py');
    const pythonExe = path.join(projectRoot, 'backend', 'venv', 'bin', 'python'); // Updated for macOS
    backendCmd = pythonExe;
    backendArgs = [runPy];
    backendCwd = projectRoot;
    if (!fs.existsSync(pythonExe) || !fs.existsSync(runPy)) {
      safeSend('backend-event', { event: 'startup_error', code: 'DEV_SETUP_MISSING', message: 'python or run.py not found (expected backend/venv/bin/python + run.py)' });
      return;
    }
  }

  backendProc = spawn(backendCmd, backendArgs, {
    cwd: backendCwd,
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe']
  });

  safeSend("backend-event", { event: "launcher_spawned", mode });
  startWatchdog();

  // Process-level error (spawn failure, permission, missing exe)
  backendProc.on('error', err => {
    safeSend("backend-event", { event: "startup_error", code: "SPAWN_FAIL", message: String(err), mode });
  });

  backendProc.on('exit', code => {
    safeSend("backend-event", { event: "backend_exit", code, mode });
    if (!backendReady && !startupError) {
      safeSend("backend-event", { event: "startup_error", code: "EXIT_BEFORE_READY", message: `Backend exited early (${code})`, mode });
    }
  });

  backendProc.stdout.on('data', chunk => {
    stdoutBuffer += chunk.toString();
    const lines = stdoutBuffer.split(/\r?\n/); stdoutBuffer = lines.pop();
    lines.forEach(l => handleBackendLine(l, false));
  });

  backendProc.stderr.on('data', chunk => {
    stderrBuffer += chunk.toString();
    const lines = stderrBuffer.split(/\r?\n/); stderrBuffer = lines.pop();
    lines.forEach(l => handleBackendLine(l, true));
  });
}

async function createWindow() {
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

    mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
      const csp = [
        "default-src 'self' 'unsafe-inline' data: blob:",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
        "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws: wss: https://script.google.com https://script.googleusercontent.com",
        "img-src 'self' data: blob: https:",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' data: https://fonts.gstatic.com",
        "frame-src https://docs.google.com https://script.google.com"
      ].join('; ');

      callback({
        responseHeaders: {
          ...details.responseHeaders,
          "Content-Security-Policy": [csp],
        }
      });
    });

    await mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY); 
    spawnBackend(); 

  mainWindow.webContents.on('did-finish-load', () => {
    if (backendReady) {
      safeSend("backend-event", lastReadyPayload || { event: "ready" });
    }
  });

  ipcMain.handle('dialog:openDirectory', async () => {
    const { filePaths } = await dialog.showOpenDialog({ properties: ['openDirectory'] });
    return filePaths[0];
  });

  ipcMain.handle('backend:restart', async () => { spawnBackend(); return true; });

  ipcMain.handle('backend:getStatus', () => ({ backendReady, lastReadyPayload }));
  
  // IPC: get app packaging status
  ipcMain.handle('app:isPackaged', () => app.isPackaged);
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { app.quit(); });
app.on('before-quit', () => { if (backendProc) backendProc.kill(); });
