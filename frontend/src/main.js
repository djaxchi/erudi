const { app, BrowserWindow, ipcMain, dialog} = require("electron");
const path = require("node:path");

// Add this line to define the entry point
const MAIN_WINDOW_WEBPACK_ENTRY = process.env.MAIN_WINDOW_WEBPACK_ENTRY || 'http://localhost:3000';

if (require("electron-squirrel-startup")) {
  app.quit();
}

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

  mainWindow.webContents.openDevTools();
};

app.commandLine.appendSwitch("no-sandbox")

app.whenReady().then(() => {
  createWindow();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
