const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("node:path");
const { spawn } = require("child_process");

if (require("electron-squirrel-startup")) {
  app.quit();
}

let backendProcess = null;

const createWindow = () => {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      additionalArguments: [
        "--csp=default-src 'self'; connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws://127.0.0.1:8000 ws://localhost:3000; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';",
      ],
      preload: path.join(
        __dirname,
        "..",
        "..",
        "..",
        "frontend",
        "src",
        "preload.js"
      ),
      nodeIntegration: false,
      contextIsolation: true,
    },
    autoHideMenuBar: true,
  });

  mainWindow.webContents.session.clearCache();

  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  ipcMain.handle("dialog:openDirectory", async () => {
    const result = await dialog.showOpenDialog({
      properties: ["openDirectory"],
    });
    return result.filePaths[0];
  });

  // CSP pour production et dev
  mainWindow.webContents.session.webRequest.onHeadersReceived(
    (details, callback) => {
      const isDev = !app.isPackaged;
      const csp = isDev
        ? "default-src 'self'; connect-src 'self' http://localhost:8000/ http://127.0.0.1:8000/ ws://localhost:3000 ws://127.0.0.1:8000/; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline';"
        : "default-src 'self'; connect-src 'self' http://localhost:8000/ http://127.0.0.1:8000/; script-src 'self'; style-src 'self';";

      callback({
        responseHeaders: {
          ...details.responseHeaders,
          "Content-Security-Policy": [csp],
        },
      });
    }
  );

  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools();
  }
};

app.commandLine.appendSwitch("no-sandbox");

app.whenReady().then(() => {
  // Lancer le backend uniquement si packagé (pour ne pas gêner le dev)
  if (app.isPackaged) {
    const backendPath = path.join(__dirname, "erudi-backend.exe");
    backendProcess = spawn(backendPath);

    backendProcess.stdout.on("data", (data) => {
      console.log(`[BACKEND STDOUT]: ${data}`);
    });

    backendProcess.stderr.on("data", (data) => {
      console.error(`[BACKEND ERROR]: ${data}`);
    });

    backendProcess.on("close", (code) => {
      console.log(`[BACKEND CLOSED] code: ${code}`);
    });
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    if (backendProcess) {
      backendProcess.kill();
    }
    app.quit();
  }
});