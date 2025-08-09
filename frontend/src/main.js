const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const waitOn = require("wait-on");

// Enable remote debugging for renderer inspection
app.commandLine.appendSwitch("remote-debugging-port", "9222");

let backendProc;

async function createWindow() {
  // 1) Launch the Python backend directly
  const backendExe = path.join(process.resourcesPath, "backend", "backend.exe");
  const backendDir = path.dirname(backendExe);

  backendProc = spawn(backendExe, [], {
    cwd: backendDir,
    // Hide backend console window in packaged mode, show in dev for debugging
    windowsHide: app.isPackaged,
    stdio: ["ignore", "pipe", "pipe"]
  });

  backendProc.on("error", err => {
    console.error("Failed to spawn backend:", err);
  });
  backendProc.on("exit", code => {
    console.log(`Backend exited with code ${code}`);
    // Optionally quit the app if backend terminates
    // app.quit();
  });

  // 2) Wait for FastAPI to become available
  try {
    await waitOn({ resources: ["http://127.0.0.1:8000/health"], timeout: 10000 });
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
      devTools: true
    },
  });

  // Capture renderer failures
  mainWindow.webContents.on("did-fail-load", (_, code, desc, url) => {
    console.error(`Failed to load ${url}: [${code}] ${desc}`);
  });
  mainWindow.webContents.on("crashed", () => {
    console.error("Renderer process crashed");
  });
  mainWindow.on("unresponsive", () => {
    console.error("Window is unresponsive");
  });

  if (!app.isPackaged) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }
  backendProc.stdout.on("data", chunk => {
    const msg = chunk.toString();
    console.log("[BACKEND]", msg);
    mainWindow.webContents.send("backend-log", msg);
  });
  backendProc.stderr.on("data", chunk => {
    const err = chunk.toString();
    console.error("[BACKEND ERROR]", err);
    mainWindow.webContents.send("backend-log-error", err);
  });

  // 5) Load the React UI
  await mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  // 6) IPC handler for directory dialog
  ipcMain.handle("dialog:openDirectory", async () => {
    const { filePaths } = await dialog.showOpenDialog({ properties: ["openDirectory"] });
    return filePaths[0];
  });
}

// App lifecycle
app.whenReady().then(createWindow);
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("before-quit", () => { if (backendProc) backendProc.kill(); });
