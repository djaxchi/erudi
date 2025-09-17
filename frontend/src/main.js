const { app, BrowserWindow, ipcMain, dialog} = require("electron");
const path = require("node:path");
const { spawn } = require("child_process");
const fs = require('fs');
const os = require('os');

// Add this line to define the entry point
const MAIN_WINDOW_WEBPACK_ENTRY = process.env.MAIN_WINDOW_WEBPACK_ENTRY || 'http://localhost:3000';

let mockBackendProcess = null;

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

const startMockBackend = () => {
  return new Promise((resolve, reject) => {
    log('Starting Python mock backend server...');
    
    const PORT = 8000;
    
    // Path to the Python mock backend
    let backendPath;
    if (app.isPackaged) {
      // In packaged app, backend is in the resources directory
      backendPath = path.join(process.resourcesPath, 'mock-backend', 'server.py');
    } else {
      // In development, backend is relative to the frontend directory
      backendPath = path.join(__dirname, '..', '..', '..', 'mock-backend', 'server.py');
    }
    
    // Check if Python backend exists
    if (!fs.existsSync(backendPath)) {
      const error = `Python backend not found at: ${backendPath}`;
      log(error);
      reject(new Error(error));
      return;
    }
    
    // Spawn Python process
    const pythonPath = '/opt/anaconda3/bin/python3';
    log(`Spawning Python backend: ${pythonPath} ${backendPath} ${PORT}`);
    const workingDir = path.dirname(backendPath);
    log(`Working directory: ${workingDir}`);
    
    mockBackendProcess = spawn(pythonPath, [backendPath, PORT.toString()], {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: workingDir
    });
    
    // Handle process output
    mockBackendProcess.stdout.on('data', (data) => {
      const output = data.toString().trim();
      log(`Backend stdout: ${output}`);
    });
    
    mockBackendProcess.stderr.on('data', (data) => {
      const output = data.toString().trim();
      log(`Backend stderr: ${output}`);
    });
    
    // Handle process exit
    mockBackendProcess.on('exit', (code, signal) => {
      log(`Backend process exited with code ${code}, signal ${signal}`);
      mockBackendProcess = null;
    });
    
    // Handle process errors
    mockBackendProcess.on('error', (error) => {
      log(`Failed to start backend process: ${error.message}`);
      reject(error);
    });
    
    // Wait for the server to start (check health endpoint)
    const checkHealth = async () => {
      for (let i = 0; i < 30; i++) {
        try {
          log(`Health check attempt ${i + 1}/30`);
          const response = await fetch(`http://127.0.0.1:${PORT}/health`);
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
      if (mockBackendProcess) {
        mockBackendProcess.kill();
        mockBackendProcess = null;
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
  log('App ready, starting mock backend...');
  try {
    // Start the mock backend first
    await startMockBackend();
    log('Mock backend started successfully, creating window...');
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
  // Stop the Python backend process when the app closes
  if (mockBackendProcess) {
    log('Shutting down Python backend process...');
    mockBackendProcess.kill('SIGTERM');
    mockBackendProcess = null;
  }
  
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  // Ensure the Python backend process is stopped when quitting
  if (mockBackendProcess) {
    log('Stopping Python backend process before quit...');
    mockBackendProcess.kill('SIGTERM');
    mockBackendProcess = null;
  }
});
