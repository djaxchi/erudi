const { app, BrowserWindow, ipcMain, dialog} = require("electron");
const path = require("node:path");
const { fork } = require("child_process");

// Add this line to define the entry point
const MAIN_WINDOW_WEBPACK_ENTRY = process.env.MAIN_WINDOW_WEBPACK_ENTRY || 'http://localhost:3000';

let mockBackendProcess = null;

if (require("electron-squirrel-startup")) {
  app.quit();
}

const startMockBackend = () => {
  // Use absolute path to the mock backend in the frontend folder
  const backendPath = path.join(__dirname, '..', '..', 'mock-backend.js');
  console.log('Starting mock backend from:', backendPath);
  console.log('__dirname is:', __dirname);
  
  // Check if file exists
  const fs = require('fs');
  if (!fs.existsSync(backendPath)) {
    console.error('Mock backend file not found at:', backendPath);
    // Try alternative path
    const altPath = path.join(process.cwd(), 'mock-backend.js');
    console.log('Trying alternative path:', altPath);
    if (fs.existsSync(altPath)) {
      console.log('Found mock backend at alternative path');
      mockBackendProcess = fork(altPath, [], {
        silent: false,
        stdio: 'inherit'
      });
    } else {
      console.error('Mock backend not found at alternative path either');
      return Promise.resolve();
    }
  } else {
    mockBackendProcess = fork(backendPath, [], {
      silent: false,
      stdio: 'inherit'
    });
  }
  
  mockBackendProcess.on('error', (error) => {
    console.error('Mock backend error:', error);
  });
  
  mockBackendProcess.on('exit', (code) => {
    console.log(`Mock backend exited with code ${code}`);
  });
  
  // Give the backend a moment to start
  return new Promise((resolve) => {
    setTimeout(resolve, 2000);
  });
};

const createWindow = () => {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, '..', '..', '..', 'frontend', 'src', 'preload.js'),
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

  // Ouvrir l'explorateur de fichiers et récupérer le chemin
  ipcMain.handle('dialog:openDirectory', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory']
    });
    return result.filePaths[0];
  });

  // Only open dev tools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }
};

app.commandLine.appendSwitch("no-sandbox")

app.whenReady().then(async () => {
  // Start the mock backend first
  await startMockBackend();
  createWindow();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on("window-all-closed", () => {
  // Kill the mock backend when the app closes
  if (mockBackendProcess) {
    mockBackendProcess.kill();
    mockBackendProcess = null;
  }
  
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  // Ensure the mock backend is killed when quitting
  if (mockBackendProcess) {
    mockBackendProcess.kill();
    mockBackendProcess = null;
  }
});
