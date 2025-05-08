const { app, BrowserWindow } = require("electron");
const path = require("node:path");

if (require("electron-squirrel-startup")) {
  app.quit();
}

const createWindow = () => {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
    },
    autoHideMenuBar: true,
  });

  mainWindow.webContents.session.clearCache();

  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

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
