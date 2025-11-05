const { app, BrowserWindow, ipcMain, dialog, Menu, shell } = require("electron");
const path = require("node:path");
const { spawn } = require("child_process");
const fs = require('fs');
const os = require('os');

// define the entry points
const MAIN_WINDOW_WEBPACK_ENTRY = process.env.MAIN_WINDOW_WEBPACK_ENTRY || 'http://localhost:3000';
const MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY = process.env.MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY;

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
    
    // In development mode, assume backend is already running via dev-start.sh
    if (!app.isPackaged) {
      log('Development mode: assuming backend is running via dev-start.sh');
      // Just check if backend is responding
      const checkDevBackendHealth = async () => {
        for (let i = 0; i < 10; i++) {
          try {
            log(`Dev backend health check attempt ${i + 1}/10`);
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2000);
            
            const response = await fetch(`http://127.0.0.1:8000/main_window/health`, {
              signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            if (response.ok) {
              const data = await response.json();
              log(`Backend is ready: ${data.message}`);
              resolve();
              return;
            }
          } catch (error) {
            log(`Dev backend health check failed: ${error.message}`);
          }
          
          // Wait before next attempt
          await new Promise(r => setTimeout(r, 1000));
        }
        
        // If we get here, backend is not responding
        log('Backend is not responding. Make sure to run: ./build-scripts/dev-start.sh');
        reject(new Error('Backend is not responding on localhost:8000'));
      };
      
      checkDevBackendHealth();
      return;
    }
    
    // Production mode: spawn packaged backend
    const PORT = 8000;
    
    // Kill any existing process on the port first
    const killExistingBackend = () => {
      return new Promise((killResolve) => {
        log('Checking for existing backend process...');
        
        // Kill our tracked process
        if (backendProcess) {
          log('Killing tracked backend process...');
          try {
            process.kill(-backendProcess.pid); // Kill process group
          } catch (e) {
            log(`Could not kill process group: ${e.message}`);
          }
          backendProcess = null;
          setTimeout(killResolve, 800);
        } else {
          // Try to kill any process on port 8000
          const { execSync } = require('child_process');
          try {
            const result = execSync('lsof -ti:8000', { encoding: 'utf-8' }).trim();
            if (result) {
              log(`Found process on port 8000: ${result}`);
              execSync(`kill -9 ${result}`, { stdio: 'ignore' });
              log('Killed process on port 8000');
            }
          } catch (e) {
            log('No existing process on port 8000 or lsof not available');
          }
          setTimeout(killResolve, 800);
        }
      });
    };
    
    killExistingBackend().then(() => {
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
        env: backendEnv,
        detached: false // Don't detach, so we can properly kill it
      });
      
      log(`Backend process spawned with PID: ${backendProcess.pid}`);
      
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
        let lastError = null;
        let consecutiveFailures = 0;
        
        for (let i = 0; i < 30; i++) {
          try {
            log(`Health check attempt ${i + 1}/30`);
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2000);
            
            const response = await fetch(`http://127.0.0.1:8000/main_window/health`, {
              signal: controller.signal
            });
            clearTimeout(timeoutId);
            
            if (response.ok) {
              const data = await response.json();
              log(`Backend is ready: ${data.message}`);
              consecutiveFailures = 0; // Reset on success
              resolve();
              return;
            }
            consecutiveFailures++;
          } catch (error) {
            lastError = error.message;
            consecutiveFailures++;
            
            // If we've had 3 consecutive failures, try to restart backend
            if (consecutiveFailures >= 3) {
              log(`${consecutiveFailures} consecutive health check failures. Attempting backend restart...`);
              
              // Kill current backend
              if (backendProcess) {
                try {
                  process.kill(-backendProcess.pid);
                } catch (e) {
                  log(`Could not kill process: ${e.message}`);
                }
                backendProcess = null;
              }
              
              // Kill any process on port 8000
              const { execSync } = require('child_process');
              try {
                const result = execSync('lsof -ti:8000', { encoding: 'utf-8' }).trim();
                if (result) {
                  log(`Killing process on port 8000: ${result}`);
                  execSync(`kill -9 ${result}`, { stdio: 'ignore' });
                }
              } catch (e) {
                // Ignore errors
              }
              
              // Wait and restart
              await new Promise(resolve => setTimeout(resolve, 1000));
              consecutiveFailures = 0;
              
              log('Restarting backend after failures...');
              reject(new Error('Backend restart needed'));
              return;
            }
          }
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
        const error = `Backend failed to start within 30 seconds. Last error: ${lastError}`;
        log(error);
        if (backendProcess) {
          log('Killing stuck backend process...');
          try {
            process.kill(-backendProcess.pid);
          } catch (e) {
            log(`Could not kill process: ${e.message}`);
          }
          backendProcess = null;
        }
        reject(new Error(error));
      };
      
      setTimeout(checkHealth, 2000);
    });
  });
};

// Create application menu with Help options
const createApplicationMenu = () => {
  const isMac = process.platform === 'darwin';
  
  const template = [
    // App menu (macOS only)
    ...(isMac ? [{
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    }] : []),
    
    // File menu
    {
      label: 'File',
      submenu: [
        isMac ? { role: 'close' } : { role: 'quit' }
      ]
    },
    
    // Edit menu
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        ...(isMac ? [
          { role: 'pasteAndMatchStyle' },
          { role: 'delete' },
          { role: 'selectAll' },
          { type: 'separator' },
          {
            label: 'Speech',
            submenu: [
              { role: 'startSpeaking' },
              { role: 'stopSpeaking' }
            ]
          }
        ] : [
          { role: 'delete' },
          { type: 'separator' },
          { role: 'selectAll' }
        ])
      ]
    },
    
    // View menu
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    
    // Window menu
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        ...(isMac ? [
          { type: 'separator' },
          { role: 'front' },
          { type: 'separator' },
          { role: 'window' }
        ] : [
          { role: 'close' }
        ])
      ]
    },
    
    // Help menu
    {
      role: 'help',
      submenu: [
        {
          label: 'Open Data Folder',
          click: async () => {
            try {
              const dataDir = getDataDirectory();
              
              // Create directory if it doesn't exist
              if (!fs.existsSync(dataDir)) {
                fs.mkdirSync(dataDir, { recursive: true });
              }
              
              // Open in Finder
              shell.openPath(dataDir);
              log(`Opened data folder: ${dataDir}`);
            } catch (error) {
              log(`Failed to open data folder: ${error.message}`);
              dialog.showErrorBox('Error', `Failed to open data folder: ${error.message}`);
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Clear All Data...',
          click: async () => {
            try {
              if (!mainWindow) {
                log('Cannot clear data: no main window');
                return;
              }
              
              const dataDir = getDataDirectory();
              
              // Show confirmation dialog
              const result = await dialog.showMessageBox(mainWindow, {
                type: 'warning',
                buttons: ['Cancel', 'Delete All Data'],
                defaultId: 0,
                cancelId: 0,
                title: 'Clear All Data',
                message: 'Are you sure you want to delete all data?',
                detail: 'This will permanently delete:\n• All downloaded AI models\n• Conversation history\n• Custom settings\n• Knowledge bases\n\nThis action cannot be undone.\n\nThe application will quit after deletion.'
              });
              
              if (result.response === 1) { // User clicked "Delete All Data"
                log('User confirmed data deletion. Clearing all data...');
                
                // Kill backend process first
                if (backendProcess) {
                  log('Stopping backend process...');
                  backendProcess.kill('SIGTERM');
                  backendProcess = null;
                }
                
                // Wait a bit for backend to shut down
                await new Promise(resolve => setTimeout(resolve, 1000));
                
                // Delete the data directory
                if (fs.existsSync(dataDir)) {
                  const { execSync } = require('child_process');
                  try {
                    execSync(`rm -rf "${dataDir}"`, { stdio: 'ignore' });
                    log(`Successfully deleted data directory: ${dataDir}`);
                  } catch (error) {
                    log(`Failed to delete data directory: ${error.message}`);
                    throw error;
                  }
                }
                
                // Show success message
                await dialog.showMessageBox(mainWindow, {
                  type: 'info',
                  buttons: ['OK'],
                  title: 'Data Cleared',
                  message: 'All data has been deleted successfully.',
                  detail: 'The application will now quit.'
                });
                
                // Quit the app
                app.quit();
              } else {
                log('User cancelled data deletion');
              }
            } catch (error) {
              log(`Failed to clear data: ${error.message}`);
              dialog.showErrorBox('Error', `Failed to clear data: ${error.message}`);
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Learn More',
          click: async () => {
            await shell.openExternal('https://github.com/djaxchi/erudi');
          }
        }
      ]
    }
  ];
  
  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
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
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY || path.join(__dirname, "preload.js"),
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

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on('closed', () => {
    log('Main window closed');
    mainWindow = null;
    isCreatingWindow = false;
    
    // Clean up backend on window close
    if (backendProcess) {
      log('Terminating backend process on window close...');
      backendProcess.kill('SIGTERM');
      backendProcess = null;
    }
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

// Handler to open files and folders for knowledge base
ipcMain.handle('dialog:openFilesAndFolders', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile', 'openDirectory', 'multiSelections'],
    filters: [
      { name: 'Documents', extensions: ['pdf', 'txt'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  });
  
  log(`Dialog result - canceled: ${result.canceled}, filePaths: ${JSON.stringify(result.filePaths)}`);
  
  if (result.canceled) {
    return [];
  }
  
  return result.filePaths;
});

// Helper function to get Application Support data directory path
function getDataDirectory() {
  const appName = 'erudi';
  return path.join(os.homedir(), 'Library', 'Application Support', appName);
}

// IPC handler to open data folder in Finder
ipcMain.handle('data:openFolder', async () => {
  try {
    const dataDir = getDataDirectory();
    
    // Create directory if it doesn't exist
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    // Open in Finder
    shell.openPath(dataDir);
    log(`Opened data folder: ${dataDir}`);
    return { success: true, path: dataDir };
  } catch (error) {
    log(`Failed to open data folder: ${error.message}`);
    return { success: false, error: error.message };
  }
});

// IPC handler to clear all data and quit
ipcMain.handle('data:clearAll', async () => {
  try {
    const dataDir = getDataDirectory();
    
    // Show confirmation dialog
    const result = await dialog.showMessageBox(mainWindow, {
      type: 'warning',
      buttons: ['Cancel', 'Delete All Data'],
      defaultId: 0,
      cancelId: 0,
      title: 'Clear All Data',
      message: 'Are you sure you want to delete all data?',
      detail: 'This will permanently delete:\n• All downloaded AI models\n• Conversation history\n• Custom settings\n• Knowledge bases\n\nThis action cannot be undone.\n\nThe application will quit after deletion.'
    });
    
    if (result.response === 1) { // User clicked "Delete All Data"
      log('User confirmed data deletion. Clearing all data...');
      
      // Kill backend process first
      if (backendProcess) {
        log('Stopping backend process...');
        backendProcess.kill('SIGTERM');
        backendProcess = null;
      }
      
      // Wait a bit for backend to shut down
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Delete the data directory
      if (fs.existsSync(dataDir)) {
        const { execSync } = require('child_process');
        try {
          execSync(`rm -rf "${dataDir}"`, { stdio: 'ignore' });
          log(`Successfully deleted data directory: ${dataDir}`);
        } catch (error) {
          log(`Failed to delete data directory: ${error.message}`);
          throw error;
        }
      }
      
      // Show success message
      await dialog.showMessageBox(mainWindow, {
        type: 'info',
        buttons: ['OK'],
        title: 'Data Cleared',
        message: 'All data has been deleted successfully.',
        detail: 'The application will now quit.'
      });
      
      // Quit the app
      app.quit();
      
      return { success: true };
    } else {
      log('User cancelled data deletion');
      return { success: false, cancelled: true };
    }
  } catch (error) {
    log(`Failed to clear data: ${error.message}`);
    
    await dialog.showMessageBox(mainWindow, {
      type: 'error',
      buttons: ['OK'],
      title: 'Error',
      message: 'Failed to clear data',
      detail: error.message
    });
    
    return { success: false, error: error.message };
  }
});

app.whenReady().then(async () => {
  log('App ready. Attempting to start backend...');
  
  // Create application menu
  createApplicationMenu();
  
  // Kill any lingering backend processes before starting
  try {
    const { execSync } = require('child_process');
    try {
      execSync('lsof -ti:8000 | xargs kill -9', { stdio: 'ignore' });
      log('Killed any existing process on port 8000');
      // Wait a bit for port to be released
      await new Promise(resolve => setTimeout(resolve, 1000));
    } catch (e) {
      log('No existing process on port 8000');
    }
  } catch (error) {
    log('Error killing existing process: ' + error.message);
  }
  
  // Retry logic for backend startup
  let retries = 0;
  const maxRetries = 3;
  
  const tryStartBackend = async () => {
    try {
      // In development mode, skip backend startup - assume user runs it separately
      if (!app.isPackaged) {
        log('Development mode: skipping backend startup (run backend separately)');
        createWindow();
        return;
      }
      
      await startRealBackend();
      log('Real backend started successfully, creating window...');
      createWindow();
    } catch (error) {
      retries++;
      log(`Backend start attempt ${retries} failed: ${error.toString()}`);
      
      if (retries < maxRetries) {
        log(`Retrying backend startup in 2 seconds... (attempt ${retries + 1}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, 2000));
        await tryStartBackend();
      } else {
        log(`Backend startup failed after ${maxRetries} attempts. Creating window without backend.`);
        createWindow();
      }
    }
  };
  
  await tryStartBackend();
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
