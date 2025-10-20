const { app, BrowserWindow, ipcMain, dialog} = require("electron");
const path = require("node:path");
const { spawn } = require("child_process");
const fs = require('fs');
const os = require('os');

// Add this line to define the entry point
const MAIN_WINDOW_WEBPACK_ENTRY = process.env.MAIN_WINDOW_WEBPACK_ENTRY || 'http://localhost:3000';

let backendProcess = null;
let mainWindow = null;
let isCreatingWindow = false;

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
    path.join(process.resourcesPath, 'backend', 'backend', 'backend'), 
    path.join(process.resourcesPath, 'backend', 'backend'), 
    path.join(process.resourcesPath, 'app.asar.unpacked', 'backend', 'backend'), 
  ];
  
  log(`Checking packaged backend paths...`);
  log(`process.resourcesPath: ${process.resourcesPath}`);
  
  for (const c of candidates) {
    log(`Checking candidate: ${c}`);
    try {
      if (fs.existsSync(c)) {
        const stat = fs.statSync(c);
        log(`Found ${c}, isFile: ${stat.isFile()}, isExecutable: ${!!(stat.mode & 0o111)}`);
        if (stat.isFile()) {
          return c;
        }
      } else {
        log(`Path does not exist: ${c}`);
      }
    } catch (error) {
      log(`Error checking ${c}: ${error.message}`);
    }
  }
  return null;
}

const startRealBackend = () => {
  return new Promise((resolve, reject) => {
    log('Starting backend server...');
    
    const PORT = 8000;
    
    let backendPath;
    if (app.isPackaged) {
      backendPath = resolvePackagedBackendPath();
    } else {
      const devCandidates = [
        path.join(__dirname, '..', '..', 'backend', 'backend'),
      ];
      backendPath = devCandidates.find(p => fs.existsSync(p)) || null;
    }
    
    if (!backendPath || !fs.existsSync(backendPath)) {
      const error = `Backend executable not found. Checked path: ${backendPath || 'None'}\n` +
        `You likely need to build it first (e.g. 'pyinstaller backend.spec').`;
      log(error);
      reject(new Error(error));
      return;
    }
    
    log(`Spawning backend: ${backendPath} --port ${PORT}`);
    const workingDir = path.dirname(backendPath);
    log(`Working directory: ${workingDir}`);
    
    const backendEnv = {
      ...process.env,
      DATABASE_URL: "sqlite:///./data/erudi.db",
      CACHE_DIR: "./data/models_cache", 
      INDEXES_DIR: "./data/indexes"
    };
    
    backendProcess = spawn(backendPath, ['--port', PORT.toString()], {
      stdio: ['pipe', 'pipe', 'pipe'],
      cwd: workingDir,
      env: backendEnv
    });
    
    backendProcess.stdout.on('data', (data) => {
      const output = data.toString().trim();
      log(`Backend stdout: ${output}`);
    });
    
    backendProcess.stderr.on('data', (data) => {
      const output = data.toString().trim();
      log(`Backend stderr: ${output}`);
    });
    
    backendProcess.on('exit', (code, signal) => {
      log(`Backend process exited with code ${code}, signal ${signal}`);
      backendProcess = null;
    });
    
    backendProcess.on('error', (error) => {
      log(`Failed to start backend process: ${error.message}`);
      if (process.platform === 'darwin') {
        log('On macOS, the first run of an unsigned binary may be blocked.');
        log('If you see a security popup, open System Settings > Privacy & Security and allow the backend binary.');
      }
      reject(error);
    });
    
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
    
    setTimeout(checkHealth, 2000);
  });
};

const createWindow = () => {
  if (isCreatingWindow || mainWindow) {
    log('Window creation already in progress or window exists, skipping...');
    return;
  }

  if (!app.isReady()) {
    log('createWindow called before app ready; deferring until ready event.');
    return; 
  }
  
  isCreatingWindow = true;
  log('Creating main window...');
  
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "erudi - BETA",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      webSecurity: true,
    },
    autoHideMenuBar: true,
    // Personnalisation de la fenêtre - boutons à droite style Windows
    titleBarStyle: 'default',
    frame: true,
    icon: process.platform !== 'darwin' ? path.join(__dirname, '..', 'assets', 'icons', 'icon.png') : undefined,
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
    isCreatingWindow = false;
  });

  mainWindow.webContents.on('dom-ready', () => {
    mainWindow.webContents.executeJavaScript(`
      // Block navigation everywhere, but let events bubble to React
      ['dragover','drop'].forEach(type =>
        window.addEventListener(type, e => e.preventDefault(), false)
      );
    `);
  });

  mainWindow.webContents.on('will-navigate', (event) => {
    event.preventDefault(); 
  });

  mainWindow.webContents.session.clearCache();

  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 https://script.google.com https://script.googleusercontent.com; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com;"
        ]
      }
    });
  });

  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }
  
  isCreatingWindow = false;
};

app.commandLine.appendSwitch("no-sandbox")

ipcMain.handle('dialog:openDirectory', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory']
  });
  return result.filePaths[0];
});

app.whenReady().then(async () => {
  log('App ready. Attempting to start backend...');
  
  try {
    await startRealBackend();
    log('Real backend started successfully, creating window...');
    createWindow();
  } catch (error) {
    log('Backend failed to start: ' + error.toString());
    createWindow();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0 && !mainWindow) {
    createWindow();
  }
});

app.on("window-all-closed", () => {
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
  if (backendProcess) {
    log('Stopping backend process before quit...');
    backendProcess.kill('SIGTERM');
    backendProcess = null;
  }
});
