/* eslint-disable no-console */
const { app, BrowserWindow, ipcMain, dialog, Menu, shell } = require("electron");
const path = require("node:path");
const { spawn, execSync } = require("child_process");
const fs = require("fs");
const os = require("os");

// Pure, unit-tested startup helpers (shared with the renderer).
const { confirmBackendHealth } = require("./utils/backendHealth");
const { classifyStderrLine } = require("./utils/backendStderr");
const { shouldRetrySpawn } = require("./utils/backendRetry");
const { buildBackendSpawnOptions } = require("./utils/backendSpawn");
const { gracefulShutdown } = require("./utils/backendShutdown");

// electron-updater: only loaded in production to avoid dev noise.
// Reads latest.yml / latest-mac.yml from GitHub Releases and handles
// download + install of new versions.
let autoUpdater = null;
if (app.isPackaged) {
  try {
    autoUpdater = require("electron-updater").autoUpdater;
    autoUpdater.autoDownload = true; // Download silently in the background
    autoUpdater.autoInstallOnAppQuit = true; // Install on next natural quit
    autoUpdater.logger = require("electron-log");
    autoUpdater.logger.transports.file.level = "info";
  } catch (e) {
    // electron-updater not available — skip updates silently
    autoUpdater = null;
  }
}

// Renderer + preload entry resolution (replaces the @electron-forge/plugin-webpack
// magic globals). Prod (packaged): load the built files that sit next to this
// main bundle — .webpack/renderer/main_window/ — via file://. Dev: the
// webpack-dev-server serves the renderer at :3000 and writes preload.js to disk.
const MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY = path.join(
  __dirname,
  "..",
  "renderer",
  "main_window",
  "preload.js"
);
const MAIN_WINDOW_RENDERER_INDEX = path.join(
  __dirname,
  "..",
  "renderer",
  "main_window",
  "index.html"
);
const RENDERER_DEV_URL = "http://localhost:3000/";

let backendProcess = null;
let mainWindow = null;
let isCreatingWindow = false;
// Set once a quit-time graceful shutdown is in flight so before-quit runs its
// (async) teardown exactly once — the app.quit() it re-issues must fall through.
let shuttingDown = false;
// Backend readiness state, published to the renderer (covers the race where
// readiness happens before the renderer attaches its event listener — the
// renderer queries `backend:getInfo` on mount).
let resolvedPort = null;
let backendIsReady = false;
// Transient failures (port contention) may auto-respawn; deterministic ones
// fail fast and wait for a manual retry.
const MAX_SPAWN_ATTEMPTS = 2;

// Kill the backend process and its entire child tree.
// On Windows, SIGTERM only kills the parent — llama-server.exe is left orphaned.
// taskkill /F /T kills the full process tree.
function killBackend(proc) {
  if (!proc) {
    return;
  }
  if (process.platform === "win32") {
    try {
      execSync(`taskkill /F /T /PID ${proc.pid}`, { stdio: "ignore" });
    } catch (_) {
      // Process may have already exited
    }
  } else {
    try {
      // Kill the entire process group (negative PID) so uvicorn workers
      // and multiprocessing children are also terminated.
      process.kill(-proc.pid, "SIGTERM");
    } catch (_) {
      // Fallback if the process is no longer a group leader
      try {
        proc.kill("SIGTERM");
      } catch (_) {
        /* already exited */
      }
    }
  }
}

// Create a log file for debugging. This is THE file QA reads (app:getLogPath);
// renderer logs are forwarded here too via the "renderer-log" IPC channel.
const logFile = path.join(os.tmpdir(), "erudi-backend.log");
const oldLogFile = path.join(os.tmpdir(), "erudi-backend.old.log");
const LOG_MAX_BYTES = 10 * 1024 * 1024; // 10 MB size cap
const LOG_STAT_EVERY = 200; // fs.stat is cheap but not free — sample it
let logWriteCount = 0;

// Size-cap rotation: stat the file on the first write and then every
// LOG_STAT_EVERY writes; past the cap, the current file replaces
// erudi-backend.old.log and a fresh one starts. Never throws.
const rotateLogIfNeeded = () => {
  logWriteCount += 1;
  if (logWriteCount % LOG_STAT_EVERY !== 1) return;
  try {
    const { size } = fs.statSync(logFile);
    if (size <= LOG_MAX_BYTES) return;
    fs.rmSync(oldLogFile, { force: true }); // rename() won't replace on Windows
    fs.renameSync(logFile, oldLogFile);
  } catch (_) {
    // Missing file or a losing race — never let rotation break logging.
  }
};

const log = (message) => {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}\n`;
  console.log(message);
  try {
    rotateLogIfNeeded();
    fs.appendFileSync(logFile, logMessage);
  } catch (err) {
    console.error("Failed to write to log file:", err);
  }
};

log(`Starting app, log file: ${logFile}`);

if (require("electron-squirrel-startup")) {
  app.quit();
}

function resolvePackagedBackendPath() {
  // On Windows PyInstaller produces backend.exe; on macOS/Linux just backend
  const exeSuffix = process.platform === "win32" ? ".exe" : "";
  // Candidate locations inside the packaged app
  const candidates = [
    path.join(process.resourcesPath, "backend", `backend${exeSuffix}`),
    path.join(process.resourcesPath, "backend", "backend", `backend${exeSuffix}`),
    path.join(process.resourcesPath, "app.asar.unpacked", "backend", `backend${exeSuffix}`),
  ];

  log("Checking packaged backend paths...");
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
    log("Starting backend server...");

    // In development mode, assume backend is already running via dev-start.sh
    if (!app.isPackaged) {
      log("Development mode: assuming backend is running via dev-start.sh");
      // Just check if backend is responding
      const checkDevBackendHealth = async () => {
        const devPort = process.env.BACKEND_PORT || "27182";
        log(`Dev mode using port: ${devPort}`);

        for (let i = 0; i < 10; i++) {
          try {
            log(`Dev backend health check attempt ${i + 1}/10`);
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 2000);

            const response = await fetch(`http://127.0.0.1:${devPort}/erudi/health/`, {
              signal: controller.signal,
            });
            clearTimeout(timeoutId);

            if (response.ok) {
              const data = await response.json();
              log(`Backend is ready: ${data.message}`);
              resolve({ port: Number(devPort) });
              return;
            }
          } catch (error) {
            log(`Dev backend health check failed: ${error.message}`);
          }

          // Wait before next attempt
          await new Promise((r) => setTimeout(r, 1000));
        }

        // If we get here, backend is not responding
        log(
          "Backend is not responding. Make sure to run: ./build-scripts/dev-start.sh or set BACKEND_PORT env variable"
        );
        reject(new Error(`Backend is not responding on localhost:${devPort}`));
      };

      checkDevBackendHealth();
      return;
    }

    // Production mode: spawn packaged backend.
    // 27182 = Erudi's canonical port (digits of e, for erudites — see backend/run.py).
    const PORT = 27182;

    // The backend owns port selection: it scans 27182–27199 and announces the
    // resolved port back to us via its JSON lifecycle events (we forward it to the
    // renderer), so it's fine if this exact port is taken.
    let backendPath;
    if (app.isPackaged) {
      backendPath = resolvePackagedBackendPath();
    } else {
      const exeSuffix = process.platform === "win32" ? ".exe" : "";
      const devCandidates = [
        path.join(__dirname, "..", "..", "backend", "dist", "backend", `backend${exeSuffix}`),
        path.join(__dirname, "..", "..", "backend", "backend"),
      ];
      backendPath = devCandidates.find((p) => fs.existsSync(p)) || null;
    }

    if (!backendPath || !fs.existsSync(backendPath)) {
      const error =
        `Backend executable not found. Checked path: ${backendPath || "None"}\n` +
        "You likely need to build it first (e.g. 'pyinstaller backend.spec').";
      log(error);
      reject(new Error(error));
      return;
    }

    log(`Spawning backend: ${backendPath} --port ${PORT}`);
    const workingDir = path.dirname(backendPath);
    log(`Working directory: ${workingDir}`);

    // Storage paths (embedded PostgreSQL data dir, model cache) are resolved
    // by the backend itself (src/launcher/runtime_paths.py) — nothing to pass.
    // PYTHONUTF8=1 only affects the NON-frozen (dev) interpreter: PyInstaller's
    // bootloader pre-initializes CPython and ignores this env var, so the
    // packaged build gets UTF-8 mode from the spec's interpreter OPTIONS instead
    // (see backend/backend.spec, #168). We still set it here because in dev it
    // makes open() read bundled data files (e.g. alembic.ini) as UTF-8 regardless
    // of the locale — a macOS app launched from Finder inherits no LANG (see #149).
    // ERUDI_WATCH_STDIN=1 opts the launcher into watching stdin for EOF: on quit
    // we close stdin so the backend shuts down gracefully (stop_postgres), which
    // Windows otherwise never got because taskkill /F /T skips the lifespan (#216).
    const backendEnv = { ...process.env, PYTHONUTF8: "1", ERUDI_WATCH_STDIN: "1" };

    backendProcess = spawn(
      backendPath,
      ["--port", PORT.toString()],
      buildBackendSpawnOptions(process.platform, { cwd: workingDir, env: backendEnv })
    );

    log(`Backend process spawned with PID: ${backendProcess.pid}`);

    const proc = backendProcess;
    let settled = false;
    let actualPort = PORT;
    let capTimer = null;
    const settle = (fn) => (arg) => {
      if (settled) return;
      settled = true;
      if (capTimer) clearTimeout(capTimer);
      fn(arg);
    };
    const succeed = settle(() => resolve({ port: actualPort }));
    // reject carries the error CODE (string) so the supervisor can classify it.
    const failWith = settle((code) => reject(new Error(code)));

    // Absolute safety cap. The backend self-aborts at its own first-run-aware
    // budget (300s first run / 120s after) and emits startup_error, which we
    // catch below; this only fires if it goes completely silent. We NEVER kill
    // the backend just for being slow — that was the 30s-kill bug.
    const MAX_READY_WAIT_MS = 330000;
    capTimer = setTimeout(() => {
      log("Backend did not report ready within the safety cap.");
      failWith("PORT_TIMEOUT");
    }, MAX_READY_WAIT_MS);

    backendProcess.stdout.on("data", (data) => {
      for (const line of data.toString().split(/\r?\n/)) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        log(`Backend stdout: ${trimmed}`);
        let event = null;
        try {
          event = JSON.parse(trimmed);
        } catch (_) {
          continue; // ordinary (non-JSON) log line
        }
        if (!event || !event.event) continue;
        // Forward every structured event to the renderer (starting/phase/ready/…).
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send("backend-event", event);
        }
        if (event.event === "starting" && event.port) {
          actualPort = event.port;
          log(`Backend selected port: ${actualPort}`);
        } else if (event.event === "startup_error") {
          log(`Backend reported startup_error: ${event.code}`);
          failWith(event.code || "BACKEND_STARTUP_FAILED");
        } else if (event.event === "ready") {
          if (event.port) actualPort = event.port;
          log(`Backend reported ready on port ${actualPort}; confirming health…`);
          confirmBackendHealth({
            fetchFn: (url) => fetch(url),
            url: `http://127.0.0.1:${actualPort}/erudi/health/`,
          })
            .then((ok) => {
              if (ok) {
                log("Backend health confirmed.");
                succeed();
              } else {
                log("Backend reported ready but health could not be confirmed.");
                failWith("BACKEND_UNREACHABLE");
              }
            })
            .catch(() => failWith("BACKEND_UNREACHABLE"));
        }
      }
    });

    backendProcess.stderr.on("data", (data) => {
      const output = data.toString().trim();
      if (!output) return;
      log(`Backend stderr: ${output}`);
      // stderr is advisory only. The backend emits authoritative startup_error
      // events on stdout; a stderr substring must never be treated as fatal — a
      // CPU build prints benign lines like "CUDA not available" / NVML / SQLAlchemy
      // "database" logs during a perfectly healthy boot. Log a hint at most.
      const hint = classifyStderrLine(output);
      if (hint) log(`stderr hint: ${hint.code} — ${hint.message}`);
    });

    backendProcess.on("exit", (code, signal) => {
      log(`Backend process exited with code ${code}, signal ${signal}`);
      if (backendProcess === proc) backendProcess = null;
      if (code === 127) {
        failWith("BACKEND_NOT_FOUND");
      } else if (code !== 0 && code !== null) {
        failWith("BACKEND_EXIT_ERROR");
      } else {
        // Clean exit before readiness was confirmed — treat as a crash. After a
        // successful start this is a no-op (the promise is already settled).
        failWith("CRASH_BEFORE_READY");
      }
    });

    backendProcess.on("error", (error) => {
      log(`Failed to start backend process: ${error.message}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("backend-event", {
          event: "startup_error",
          code: "BACKEND_SPAWN_FAILED",
          message: error.message,
          source: "spawn",
        });
      }
      failWith("BACKEND_SPAWN_FAILED");
    });
  });
};

// Supervise a backend spawn: auto-respawn only transient failures (port
// contention), fail fast + surface deterministic ones for a manual retry.
async function startBackendSupervised(attempt = 0) {
  try {
    log(`Backend startup attempt ${attempt + 1}...`);
    const { port } = await startRealBackend();
    resolvedPort = port;
    backendIsReady = true;
    log(`Backend is ready on port ${port}.`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("backend-event", { event: "backend_ready", port });
    }
  } catch (error) {
    const code = (error && error.message) || "BACKEND_STARTUP_FAILED";
    log(`Backend start attempt ${attempt + 1} failed: ${code}`);
    if (shouldRetrySpawn(code, attempt, MAX_SPAWN_ATTEMPTS)) {
      log(`Transient failure (${code}); respawning…`);
      killBackend(backendProcess);
      backendProcess = null;
      await new Promise((r) => setTimeout(r, 2000));
      return startBackendSupervised(attempt + 1);
    }
    log(`Backend startup failed (${code}); surfacing to the user.`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("backend-event", {
        event: "startup_error",
        code,
        message: (error && error.message) || code,
        source: "startup",
      });
    }
  }
}

// Create application menu with Help options
const createApplicationMenu = () => {
  const isMac = process.platform === "darwin";

  const template = [
    // App menu (macOS only)
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: "about" },
              { type: "separator" },
              { role: "services" },
              { type: "separator" },
              { role: "hide" },
              { role: "hideOthers" },
              { role: "unhide" },
              { type: "separator" },
              { role: "quit" },
            ],
          },
        ]
      : []),

    // File menu
    {
      label: "File",
      submenu: [isMac ? { role: "close" } : { role: "quit" }],
    },

    // Edit menu
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        ...(isMac
          ? [
              { role: "pasteAndMatchStyle" },
              { role: "delete" },
              { role: "selectAll" },
              { type: "separator" },
              {
                label: "Speech",
                submenu: [{ role: "startSpeaking" }, { role: "stopSpeaking" }],
              },
            ]
          : [{ role: "delete" }, { type: "separator" }, { role: "selectAll" }]),
      ],
    },

    // View menu
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },

    // Window menu
    {
      label: "Window",
      submenu: [
        { role: "minimize" },
        { role: "zoom" },
        ...(isMac
          ? [{ type: "separator" }, { role: "front" }, { type: "separator" }, { role: "window" }]
          : [{ role: "close" }]),
      ],
    },

    // Help menu
    {
      role: "help",
      submenu: [
        {
          label: "Open Data Folder",
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
              dialog.showErrorBox("Error", `Failed to open data folder: ${error.message}`);
            }
          },
        },
        { type: "separator" },
        {
          label: "Clear All Data...",
          click: async () => {
            try {
              if (!mainWindow) {
                log("Cannot clear data: no main window");
                return;
              }

              const dataDir = getDataDirectory();

              // Show confirmation dialog
              const result = await dialog.showMessageBox(mainWindow, {
                type: "warning",
                buttons: ["Cancel", "Delete All Data"],
                defaultId: 0,
                cancelId: 0,
                title: "Clear All Data",
                message: "Are you sure you want to delete all data?",
                detail:
                  "This will permanently delete:\n• All downloaded AI models\n• Conversation history\n• Custom settings\n• Knowledge bases\n\nThis action cannot be undone.\n\nThe application will quit after deletion.",
              });

              if (result.response === 1) {
                // User clicked "Delete All Data"
                log("User confirmed data deletion. Clearing all data...");

                // Stop the backend first — graceful so Postgres runs
                // stop_postgres and releases the data-dir locks we are about to
                // delete; killBackend is the hard tree-kill fallback (#216).
                if (backendProcess) {
                  log("Stopping backend process...");
                  await gracefulShutdown(backendProcess, { killFn: killBackend });
                  backendProcess = null;
                }

                // Wait a bit for the OS to release any lingering file handles
                await new Promise((resolve) => setTimeout(resolve, 1000));

                // Delete the data directory
                if (fs.existsSync(dataDir)) {
                  try {
                    fs.rmSync(dataDir, { recursive: true, force: true });
                    log(`Successfully deleted data directory: ${dataDir}`);
                  } catch (error) {
                    log(`Failed to delete data directory: ${error.message}`);
                    throw error;
                  }
                }

                // Show success message
                await dialog.showMessageBox(mainWindow, {
                  type: "info",
                  buttons: ["OK"],
                  title: "Data Cleared",
                  message: "All data has been deleted successfully.",
                  detail: "The application will now quit.",
                });

                // Quit the app
                app.quit();
              } else {
                log("User cancelled data deletion");
              }
            } catch (error) {
              log(`Failed to clear data: ${error.message}`);
              dialog.showErrorBox("Error", `Failed to clear data: ${error.message}`);
            }
          },
        },
        { type: "separator" },
        {
          label: "Learn More",
          click: async () => {
            await shell.openExternal("https://github.com/djaxchi/erudi");
          },
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
};

const createWindow = () => {
  if (isCreatingWindow || mainWindow) {
    log("Window creation already in progress or window exists, skipping...");
    return;
  }

  if (!app.isReady()) {
    log("createWindow called before app ready; deferring until ready event.");
    return;
  }

  isCreatingWindow = true;
  log("Creating main window...");

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "erudi - BETA",
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      webSecurity: true,
    },
    autoHideMenuBar: true,
    // Personnalisation de la fenêtre - boutons à droite style Windows
    titleBarStyle: "default",
    frame: true,
    icon:
      process.platform !== "darwin"
        ? path.join(__dirname, "..", "assets", "icons", "icon.png")
        : undefined,
  });

  // External links (window.open / target="_blank") must reach the system
  // browser instead of spawning a bare second Electron window.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://") || url.startsWith("http://")) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    log("Main window closed");
    mainWindow = null;
    isCreatingWindow = false;
  });

  mainWindow.webContents.on("dom-ready", () => {
    mainWindow.webContents.executeJavaScript(`
      // Block navigation everywhere, but let events bubble to React
      ['dragover','drop'].forEach(type =>
        window.addEventListener(type, e => e.preventDefault(), false)
      );
    `);
  });

  mainWindow.webContents.on("will-navigate", (event) => {
    event.preventDefault();
  });

  mainWindow.webContents.session.clearCache();

  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    // Skip header modification for backend API responses to preserve
    // chunked transfer-encoding and avoid buffering streaming responses.
    if (details.url.includes("/erudi/")) {
      callback({ cancel: false });
      return;
    }

    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [
          "default-src 'self'; connect-src 'self' http://127.0.0.1:* http://localhost:* https://script.google.com https://script.googleusercontent.com; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:;",
        ],
      },
    });
  });

  if (app.isPackaged) {
    mainWindow.loadFile(MAIN_WINDOW_RENDERER_INDEX);
  } else {
    mainWindow.loadURL(RENDERER_DEV_URL);
  }

  if (process.env.NODE_ENV === "development") {
    mainWindow.webContents.openDevTools();
  }

  isCreatingWindow = false;
};

app.commandLine.appendSwitch("no-sandbox");

// Backend readiness + diagnostics for the renderer. getInfo lets the renderer
// recover the resolved port / ready state if it mounted after the events fired
// (race-safe); restart actually re-spawns the backend (used by the Retry button).
ipcMain.handle("backend:getInfo", () => ({ port: resolvedPort, ready: backendIsReady }));
ipcMain.handle("app:getLogPath", () => logFile);

// Renderer log bridge: the renderer forwards its logger calls here (fire-and-
// forget ipcRenderer.send, see preload.js logAPI) so they persist in the same
// file QA already reads. Entries are validated defensively — a malformed
// payload is dropped, never thrown on.
const RENDERER_LOG_MAX_CHARS = 4000;
const asLogString = (value, max) => (typeof value === "string" ? value.slice(0, max) : "");
ipcMain.on("renderer-log", (_event, entry) => {
  try {
    if (!entry || typeof entry !== "object") return;
    const ns = asLogString(entry.ns, 120) || "unknown";
    const level = (asLogString(entry.level, 10) || "info").toUpperCase();
    const msg = asLogString(entry.msg, RENDERER_LOG_MAX_CHARS);
    const data = asLogString(entry.data, RENDERER_LOG_MAX_CHARS);
    log(`[renderer:${ns}] ${level} ${msg}${data ? ` ${data}` : ""}`);
  } catch (_) {
    // Logging must never crash the main process.
  }
});
ipcMain.handle("backend:restart", async () => {
  log("Renderer requested a backend restart.");
  // Graceful first (stop_postgres releases the data-dir locks) so the respawn
  // isn't racing an orphaned postmaster; killBackend is the hard fallback (#216).
  await gracefulShutdown(backendProcess, { killFn: killBackend });
  backendProcess = null;
  backendIsReady = false;
  resolvedPort = null;
  startBackendSupervised();
  return { ok: true };
});

ipcMain.handle("dialog:openDirectory", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
  });
  return result.filePaths[0];
});

ipcMain.handle("fs:readImageAsDataURL", async (_event, filePath) => {
  try {
    const data = fs.readFileSync(filePath);
    const ext = path.extname(filePath).slice(1).toLowerCase();
    const mime = ext === "jpg" ? "jpeg" : ext || "png";
    return `data:image/${mime};base64,${data.toString("base64")}`;
  } catch {
    return null;
  }
});

// Persist a pasted (clipboard) image to disk and return its absolute path.
// The renderer has no fs access, and a clipboard image has no source path, so
// it would otherwise be stored as a bare [image] placeholder and lost on reload
// (#136). Writing it under the user-data dir gives it a real path that flows
// through the same [image_path:...] persistence + fs:readImageAsDataURL reload
// pipeline as any file attachment.
ipcMain.handle("image:savePasted", async (_event, dataUrl) => {
  try {
    const match = /^data:image\/([a-zA-Z0-9.+-]+);base64,(.*)$/.exec(dataUrl || "");
    if (!match) {
      return null;
    }
    let ext = match[1].toLowerCase();
    if (ext === "jpeg") {
      ext = "jpg";
    } else if (ext === "svg+xml") {
      ext = "svg";
    }
    const bytes = Buffer.from(match[2], "base64");
    const dir = path.join(getDataDirectory(), "pasted-images");
    fs.mkdirSync(dir, { recursive: true });
    const filePath = path.join(
      dir,
      `paste-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.${ext}`
    );
    fs.writeFileSync(filePath, bytes);
    return filePath;
  } catch (error) {
    log(`Failed to save pasted image: ${error.message}`);
    return null;
  }
});

// Helper function to get the user data directory path (cross-platform)
function getDataDirectory() {
  const appName = "erudi";
  if (process.platform === "win32") {
    const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(localAppData, appName);
  }
  return path.join(os.homedir(), "Library", "Application Support", appName);
}

// IPC handler to open data folder in Finder
ipcMain.handle("data:openFolder", async () => {
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
ipcMain.handle("data:clearAll", async () => {
  try {
    const dataDir = getDataDirectory();

    // Show confirmation dialog
    const result = await dialog.showMessageBox(mainWindow, {
      type: "warning",
      buttons: ["Cancel", "Delete All Data"],
      defaultId: 0,
      cancelId: 0,
      title: "Clear All Data",
      message: "Are you sure you want to delete all data?",
      detail:
        "This will permanently delete:\n• All downloaded AI models\n• Conversation history\n• Custom settings\n• Knowledge bases\n\nThis action cannot be undone.\n\nThe application will quit after deletion.",
    });

    if (result.response === 1) {
      // User clicked "Delete All Data"
      log("User confirmed data deletion. Clearing all data...");

      // Stop the backend BEFORE deleting the data dir it holds open. Graceful
      // first so the embedded Postgres runs stop_postgres and releases its
      // locks; killBackend is the hard fallback that tears down the whole tree
      // (not a bare SIGTERM, which on Windows only hits the parent — #147/#216).
      if (backendProcess) {
        log("Stopping backend process...");
        await gracefulShutdown(backendProcess, { killFn: killBackend });
        backendProcess = null;
      }

      // Wait a bit for the OS to release any lingering file handles
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Delete the data directory
      if (fs.existsSync(dataDir)) {
        try {
          fs.rmSync(dataDir, { recursive: true, force: true });
          log(`Successfully deleted data directory: ${dataDir}`);
        } catch (error) {
          log(`Failed to delete data directory: ${error.message}`);
          throw error;
        }
      }

      // Show success message
      await dialog.showMessageBox(mainWindow, {
        type: "info",
        buttons: ["OK"],
        title: "Data Cleared",
        message: "All data has been deleted successfully.",
        detail: "The application will now quit.",
      });

      // Quit the app
      app.quit();

      return { success: true };
    } else {
      log("User cancelled data deletion");
      return { success: false, cancelled: true };
    }
  } catch (error) {
    log(`Failed to clear data: ${error.message}`);

    await dialog.showMessageBox(mainWindow, {
      type: "error",
      buttons: ["OK"],
      title: "Error",
      message: "Failed to clear data",
      detail: error.message,
    });

    return { success: false, error: error.message };
  }
});

// ── Auto-updater IPC ──────────────────────────────────────────────────────────
// Renderer can trigger an immediate install via "updater:install-now".
ipcMain.handle("updater:install-now", () => {
  if (autoUpdater) {
    autoUpdater.quitAndInstall(false, true);
  }
});

function setupAutoUpdater() {
  if (!autoUpdater) {
    return;
  }

  const send = (event, payload) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send("updater-event", { event, ...payload });
    }
  };

  autoUpdater.on("checking-for-update", () => {
    log("Updater: checking for update...");
  });

  autoUpdater.on("update-available", (info) => {
    log(`Updater: update available — v${info.version}`);
    send("update-available", { version: info.version, releaseNotes: info.releaseNotes || "" });
  });

  autoUpdater.on("update-not-available", () => {
    log("Updater: already on latest version.");
  });

  autoUpdater.on("download-progress", (progress) => {
    log(`Updater: downloading... ${Math.round(progress.percent)}%`);
    send("download-progress", { percent: Math.round(progress.percent) });
  });

  autoUpdater.on("update-downloaded", (info) => {
    log(`Updater: v${info.version} downloaded, ready to install.`);
    send("update-downloaded", { version: info.version });
  });

  autoUpdater.on("error", (err) => {
    // Log but never crash the app over an update failure
    log(`Updater error (non-fatal): ${err.message}`);
  });

  // Check on launch, then every 4 hours
  autoUpdater.checkForUpdates().catch((err) => {
    log(`Updater: initial check failed — ${err.message}`);
  });

  setInterval(
    () => {
      autoUpdater.checkForUpdates().catch((err) => {
        log(`Updater: periodic check failed — ${err.message}`);
      });
    },
    4 * 60 * 60 * 1000
  );
}

app.whenReady().then(async () => {
  log("App ready.");

  // Create application menu and window immediately — never block on backend startup.
  // The renderer handles the loading/error state via backend-event IPC messages.
  createApplicationMenu();
  createWindow();

  // Auto-updater: wire up events and kick off initial check (production only).
  setupAutoUpdater();

  if (!app.isPackaged) {
    // Dev mode: backend is expected to be already running via dev-start.sh.
    startRealBackend()
      .then(({ port }) => {
        resolvedPort = port;
        backendIsReady = true;
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send("backend-event", { event: "backend_ready", port });
        }
      })
      .catch((err) => log(`Dev backend not available: ${err.message}`));
    return;
  }

  // Production: supervise the backend in the background so the window stays
  // immediately usable (the renderer shows the loading/error state via events).
  startBackendSupervised();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0 && !mainWindow) {
    createWindow();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    // On non-macOS, closing all windows means quit. Let before-quit own the
    // backend teardown (graceful, then hard fallback) — just ask to quit.
    app.quit();
  }
  // On macOS: app stays alive in the dock after window close (standard convention).
  // Keep the backend running so re-clicking the dock icon reconnects instantly.
});

app.on("before-quit", (e) => {
  // Graceful backend shutdown before we actually quit: close stdin and give the
  // backend up to 8s to run its lifespan (checkpointer close, stop_postgres),
  // else killBackend hard-kills the tree (#216). Deferring the quit once (via
  // preventDefault) is the only way to await this; the re-issued app.quit()
  // finds shuttingDown=true and this handler falls through.
  if (!shuttingDown && backendProcess) {
    e.preventDefault();
    shuttingDown = true;
    log("Stopping backend process before quit...");
    gracefulShutdown(backendProcess, { killFn: killBackend }).finally(() => {
      backendProcess = null;
      app.quit();
    });
  }
});
