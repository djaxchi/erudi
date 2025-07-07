const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const waitOn = require("wait-on");

// Optional: enable remote-debugging so you can inspect the renderer from Chrome
app.commandLine.appendSwitch("remote-debugging-port", "9222");

let backendProc;

async function createWindow() {
  // Start Python backend
  const backendExe = path.join(process.resourcesPath, "backend", "backend.exe");
  const backendDir = path.dirname(backendExe);
  backendProc = spawn(backendExe, [], {
    cwd: backendDir,
    windowsHide: false,             
    stdio: ["ignore", "pipe", "pipe"]
  });

  backendProc.on("error", err => {
    console.error("Erreur spawn du backend :", err);
  });
  backendProc.on("exit", code => {
    console.log(`Backend exited with code ${code}`);
  });

  // Wait for FastAPI
  try {
    await waitOn({ resources: ["http://127.0.0.1:8000/health"], timeout: 10_000 });
  } catch (err) {
    console.error("Backend failed to start:", err);
  }

  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    autoHideMenuBar: true,
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      contextIsolation: true,
      nodeIntegration: false,
      devTools: true
    },
  });

  // catch renderer crashes / load failures
  mainWindow.webContents.on("did-fail-load", (_, errorCode, errorDescription, validatedURL) => {
    console.error(`❌ Failed to load ${validatedURL}: [${errorCode}] ${errorDescription}`);
  });
  mainWindow.webContents.on("crashed", () => {
    console.error("💥 Renderer process crashed");
  });
  mainWindow.on("unresponsive", () => {
    console.error("🛑 Window is unresponsive");
  });

  // backend logs
  mainWindow.webContents.openDevTools({ mode: "detach" });
  backendProc.stdout.on("data", chunk => {
    const msg = chunk.toString();
    mainWindow.webContents.send("backend-log", msg);
    console.log("[BACKEND]", msg);
  });
  backendProc.stderr.on("data", chunk => {
    const err = chunk.toString();
    mainWindow.webContents.send("backend-log-error", err);
    console.error("[BACKEND ERROR]", err);
  });

  // load UI
  await mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  // IPC handlers
  ipcMain.handle("dialog:openDirectory", async () => {
    const { filePaths } = await dialog.showOpenDialog({ properties: ["openDirectory"] });
    return filePaths[0];
  });
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("before-quit", () => { if (backendProc) backendProc.kill(); });
