const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const waitOn = require("wait-on");

// ── DO NOT redeclare these! They’re injected at build time:
//    MAIN_WINDOW_WEBPACK_ENTRY
//    MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY

let backendProc;

async function createWindow() {
  // 1) Launch the bundled backend
  const backendExe = path.join(process.resourcesPath, "backend", "backend.exe");
  backendProc = spawn(backendExe, [], { stdio: "ignore" });
  backendProc.on("exit", () => app.quit());

  // 2) Wait for FastAPI to come up
  try {
    await waitOn({ resources: ["http://127.0.0.1:8000/health"], timeout: 10_000 });
  } catch (err) {
    console.error("Backend failed to start:", err);
  }

  // 3) Create the BrowserWindow
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    autoHideMenuBar: true,
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 4) Load your renderer bundle
  await mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  // 5) IPC handler
  ipcMain.handle("dialog:openDirectory", async () => {
    const { filePaths } = await dialog.showOpenDialog({ properties: ["openDirectory"] });
    return filePaths[0];
  });
}

app.commandLine.appendSwitch("no-sandbox");

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProc) backendProc.kill();
});
