const { app, BrowserWindow, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const os = require("os");
const { spawn } = require("child_process");
const http = require("http");

const BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT = 8000;

let mainWindow = null;
let backendProc = null;

function isDev() {
  return !app.isPackaged;
}

function resourcesPath() {
  // Dans l’app packagée: MyApp.app/Contents/Resources
  return process.resourcesPath;
}

function backendDir() {
  if (isDev()) {
    // Dev: suppose que tu as copié backend/dist/backend localement ou lance un backend dev
    // Pour harmoniser avec la prod, on pointe vers ../dist/backend
    return path.resolve(__dirname, "../../dist/backend");
  }
  // Prod: Resources/backend
  return path.join(resourcesPath(), "backend");
}

function backendExecutable() {
  // binaire nommé "backend" (sans extension)
  return path.join(backendDir(), "backend");
}

function checkPort(host, port, timeoutMs = 1000) {
  return new Promise((resolve) => {
    const req = http.get({ host, port, path: "/health", timeout: timeoutMs }, (res) => {
      // /health facultatif — si pas d’endpoint health, on ne lit que le port TCP
      res.resume();
      resolve(true);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForBackendReady(maxMs = 120000, intervalMs = 250) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    const ok = await checkPort(BACKEND_HOST, BACKEND_PORT, 800);
    if (ok) return true;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}

function startBackend() {
  const execPath = backendExecutable();

  // Permissions d’exécution (au cas où)
  try { fs.chmodSync(execPath, 0o755); } catch (e) {}

  const env = {
    ...process.env,
    // Tu peux injecter un ENV pour informer le backend qu’on est packagé
    ERUDI_APP_MODE: app.isPackaged ? "production" : "development",
    ERUDI_APP_RESOURCES: resourcesPath(),
  };

  backendProc = spawn(execPath, [], {
    cwd: path.dirname(execPath),
    env,
    stdio: ["ignore", "pipe", "pipe"]
  });

  backendProc.stdout.on("data", (chunk) => {
    try {
      const line = chunk.toString().trim();
      // Option: parser JSON event
      // console.log("[backend]", line);
    } catch (_) {}
  });
  backendProc.stderr.on("data", (chunk) => {
    // console.error("[backend:err]", chunk.toString());
  });
  backendProc.on("exit", (code, signal) => {
    // Si le backend sort avant l’UI, on peut afficher une erreur
    if (mainWindow && !mainWindow.isDestroyed()) {
      dialog.showErrorBox(
        "Backend arrêté",
        `Le backend a quitté (code: ${code}, signal: ${signal}).`
      );
    }
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true
    }
  });

  const url = isDev()
    ? "http://localhost:3000"
    : "file://" + path.join(__dirname, "../renderer/index.html");

  await mainWindow.loadURL(url);

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.on("before-quit", () => {
  // Tuer le backend proprement
  if (backendProc && !backendProc.killed) {
    try {
      if (process.platform === "darwin") {
        process.kill(backendProc.pid, "SIGTERM");
      } else {
        backendProc.kill();
      }
    } catch (_) {}
  }
});

app.whenReady().then(async () => {
  // Démarrer backend d’abord
  startBackend();

  const ok = await waitForBackendReady(120000, 250);
  if (!ok) {
    dialog.showErrorBox(
      "Erreur de démarrage",
      "Le backend n’a pas répondu à temps (120s)."
    );
    app.quit();
    return;
  }

  await createWindow();

  app.on("activate", async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
