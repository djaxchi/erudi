const { app, BrowserWindow, ipcMain, dialog} = require("electron");
const path = require("node:path");

if (require("electron-squirrel-startup")) {
  app.quit();
}

const createWindow = () => {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      // preload: path.join(__dirname, 'frontend', 'src', 'preload.js'),
      preload: path.join(__dirname, '..', '..', '..', 'frontend', 'src', 'preload.js'),
      nodeIntegration: false, // Désactive l'intégration de Node.js dans le rendu
      contextIsolation: true, // Assure une isolation du contexte
    },
    autoHideMenuBar: true,
  });

  mainWindow.webContents.session.clearCache();

  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  // Ouvrir l'explorateur de fichiers et récupérer le chemin
  ipcMain.handle('dialog:openDirectory', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory']
    });
    return result.filePaths[0];  // Retourner le chemin du dossier sélectionné
  });



  // Set custom CSP headers
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    const isDev = !app.isPackaged;
    const csp = isDev
      ? "default-src 'self'; connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws://localhost:3000; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';"
      : "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self';";

    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [csp],
      },
    });
  });

  mainWindow.webContents.openDevTools();
};

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
