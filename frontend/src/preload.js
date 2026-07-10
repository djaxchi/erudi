/* eslint-disable no-console */
// See the Electron documentation for details on how to use preload scripts:
// https://www.electronjs.org/docs/latest/tutorial/process-model#preload-scripts

const { contextBridge, ipcRenderer, webUtils } = require("electron");

// Vérifie si preload.js est bien chargé
console.log("Le script preload.js est chargé");

contextBridge.exposeInMainWorld("electron", {
  // Vérifie si l'API est exposée
  openDirectory: () => {
    return ipcRenderer.invoke("dialog:openDirectory");
  },
  getFilePath: (file) => {
    if (webUtils?.getPathForFile) {
      const path = webUtils.getPathForFile(file);
      console.log("webUtils.getPathForFile returned:", path);
      return path;
    }

    console.log("Falling back to file.path:", file.path);
    return file.path;
  },
});

// Local filesystem image loader (for reloading image attachments from stored paths)
contextBridge.exposeInMainWorld("fsAPI", {
  readImageAsDataURL: (filePath) => ipcRenderer.invoke("fs:readImageAsDataURL", filePath),
});

// Pasted-image persistence: writes a clipboard image's bytes to disk and returns
// its absolute path, so a pasted attachment survives reload like a file one (#136).
contextBridge.exposeInMainWorld("imageAPI", {
  savePasted: (dataUrl) => ipcRenderer.invoke("image:savePasted", dataUrl),
});

// Expose additional API for data management
contextBridge.exposeInMainWorld("electronAPI", {
  openDataFolder: () => ipcRenderer.invoke("data:openFolder"),
  clearAllData: () => ipcRenderer.invoke("data:clearAll"),
});

// Backend lifecycle bridge: forwards run.py / main.js "backend-event" messages
// ({event: "starting"|"ready"|"shutdown"|"startup_error", code?, message?}) so the
// renderer can show a real error instead of an endless loading spinner.
contextBridge.exposeInMainWorld("backendAPI", {
  onBackendEvent: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("backend-event", handler);
    return () => ipcRenderer.removeListener("backend-event", handler);
  },
  // Recover {port, ready} if the renderer mounted after the events fired.
  getInfo: () => ipcRenderer.invoke("backend:getInfo"),
  // Actually re-spawn the backend (used by the error screen's Retry button).
  restartBackend: () => ipcRenderer.invoke("backend:restart"),
  // OS-correct path to the backend log, for the error screen.
  getLogPath: () => ipcRenderer.invoke("app:getLogPath"),
});

// Renderer log bridge: fire-and-forget forwarding of renderer logger entries
// ({ts, level, ns, msg, data}) to the main process, which persists them in the
// same log file QA already reads (see main.js "renderer-log" handler).
contextBridge.exposeInMainWorld("logAPI", {
  send: (entry) => ipcRenderer.send("renderer-log", entry),
});

// Auto-updater bridge
contextBridge.exposeInMainWorld("updaterAPI", {
  // Register a callback for updater events from main process.
  // event types: "update-available" | "download-progress" | "update-downloaded"
  onUpdaterEvent: (callback) => {
    ipcRenderer.on("updater-event", (_event, payload) => callback(payload));
    // Return cleanup function
    return () => ipcRenderer.removeAllListeners("updater-event");
  },
  // Trigger immediate quit-and-install
  installNow: () => ipcRenderer.invoke("updater:install-now"),
});
