const { app, BrowserWindow, ipcMain, dialog} = require("electron");
const path = require("node:path");
const { spawn } = require("child_process");
const fs = require('fs');
const os = require('os');

// Add this line to define the entry point
const MAIN_WINDOW_WEBPACK_ENTRY = process.env.MAIN_WINDOW_WEBPACK_ENTRY || 'http://localhost:3000';

let backendProcess = null;

// Create a log file for debugging
const logFile = path.join(os.tmpdir(), 'erudi-backend.log');
const log = (message) => {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}\n`;
  console.log(message);
  try {
    fs.appendFileSync(logFile, logMessage);
  } catch (err) {
    console.error('Failed to write to log file:', err);
  }
};

log(`Starting app, log file: ${logFile}`);

if (require("electron-squirrel-startup")) {
  app.quit();
}

function resolvePackagedBackendPath() {
  // Candidate locations inside the packaged app
  const candidates = [
    path.join(process.resourcesPath, 'backend', 'backend'), // when entire dist/backend folder copied
    path.join(process.resourcesPath, 'backend'),            // if only the executable was copied (legacy)
    path.join(process.resourcesPath, 'app.asar.unpacked', 'backend', 'backend'), // in case ASAR unpacked use
  ];
  for (const c of candidates) {
    try {
      if (fs.existsSync(c)) return c;
    } catch (_) { /* ignore */ }
  }
  return null;
}

const startRealBackend = () => {
  return new Promise((resolve, reject) => {
    log('Starting backend server...');
    
    const PORT = 8000;
    
    // Path to the real backend executable
    let backendPath;
    if (app.isPackaged) {
      backendPath = resolvePackagedBackendPath();
    } else {
      // Dev: assume you've run PyInstaller already OR just run the API via python separately.
      // Prefer a local virtualenv binary if available.
      const devCandidates = [
        path.join(__dirname, '..', '..', '..', 'dist', 'backend', 'backend'),
        path.join(__dirname, '..', '..', '..', 'build', 'backend', 'backend'),
      ];
      backendPath = devCandidates.find(p => fs.existsSync(p)) || null;
    }
    
    // Check if backend executable exists
    if (!backendPath || !fs.existsSync(backendPath)) {
      const error = `Backend executable not found. Checked path: ${backendPath || 'None'}\n` +
        `You likely need to build it first (e.g. 'pyinstaller backend.spec').`;
      log(error);
      reject(new Error(error));
      return;
    }
    
    // Spawn backend process (no need for Python interpreter)
    log(`Spawning backend: ${backendPath} --port ${PORT}`);
    const workingDir = path.dirname(backendPath);
    log(`Working directory: ${workingDir}`);
    
    backendProcess = spawn(backendPath, ['--port', PORT.toString()], {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: workingDir
    });
    
    // Handle process output
    backendProcess.stdout.on('data', (data) => {
      const output = data.toString().trim();
      log(`Backend stdout: ${output}`);
    });
    
    backendProcess.stderr.on('data', (data) => {
      const output = data.toString().trim();
      log(`Backend stderr: ${output}`);
    });
    
    // Handle process exit
    backendProcess.on('exit', (code, signal) => {
      log(`Backend process exited with code ${code}, signal ${signal}`);
      backendProcess = null;
    });
    
    // Handle process errors
    backendProcess.on('error', (error) => {
      log(`Failed to start backend process: ${error.message}`);
      // Provide macOS Gatekeeper hint
      if (process.platform === 'darwin') {
        log('On macOS, the first run of an unsigned binary may be blocked.');
        log('If you see a security popup, open System Settings > Privacy & Security and allow the backend binary.');
      }
      reject(error);
    });
    
    // Wait for the server to start (check health endpoint)
    const checkHealth = async () => {
      for (let i = 0; i < 30; i++) {
        try {
          log(`Health check attempt ${i + 1}/30`);
          const response = await fetch(`http://127.0.0.1:${PORT}/main_window/health`);
          if (response.ok) {
            const data = await response.json();
            log(`Backend is ready: ${data.message}`);
            resolve();
            return;
          }
        } catch (error) {
          // Ignore connection errors during startup
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      
      const error = 'Backend failed to start within 30 seconds';
      log(error);
      if (backendProcess) {
        backendProcess.kill();
        backendProcess = null;
      }
      reject(new Error(error));
    };
    
    // Start health checks after a brief delay
    setTimeout(checkHealth, 2000);
  });
};

const createWindow = () => {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      webSecurity: true,
    },
    autoHideMenuBar: true,
  });

  // Add global drag & drop support after DOM is ready
  mainWindow.webContents.on('dom-ready', () => {
    mainWindow.webContents.executeJavaScript(`
      // Block navigation everywhere, but let events bubble to React
      ['dragover','drop'].forEach(type =>
        window.addEventListener(type, e => e.preventDefault(), false)
      );
    `);
  });

  // Extra safety - Block any navigation the renderer still tries to start
  mainWindow.webContents.on('will-navigate', (event) => {
    event.preventDefault(); // cancel stray navigations (file://, http://, etc.)
  });

  mainWindow.webContents.session.clearCache();

  // Add CSP headers to allow backend connections
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';"
        ]
      }
    });
  });

  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  // Only open dev tools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }
};

app.commandLine.appendSwitch("no-sandbox")

// Register IPC handlers once globally
ipcMain.handle('dialog:openDirectory', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory']
  });
  return result.filePaths[0];
});

app.whenReady().then(async () => {
  log('App ready, starting backend...');
  try {
    // Start the real backend first
    await startRealBackend();
    log('Backend started successfully, creating window...');
    createWindow();
  } catch (error) {
    log('Failed to start application: ' + error.toString());
    // Create window anyway, maybe the backend will work later
    createWindow();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on("window-all-closed", () => {
  // Stop the backend process when the app closes
  if (backendProcess) {
    log('Shutting down backend process...');
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
  
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  // Ensure the backend process is stopped when quitting
  if (backendProcess) {
    log('Stopping backend process before quit...');
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
});
