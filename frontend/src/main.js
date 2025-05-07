const { app, BrowserWindow, ipcMain } = require("electron");
const os = require("os");
const si = require("systeminformation");
const path = require("path");

if (require("electron-squirrel-startup")) {
  app.quit();
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 800, height: 600,
    webPreferences: {
      preload: MAIN_WINDOW_PRELOAD_WEBPACK_ENTRY,
      contextIsolation: true,
      nodeIntegration: false,
    },
    autoHideMenuBar: true,
  });

  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);
  mainWindow.webContents.openDevTools();
}

ipcMain.handle('hardware:getStats', async () => {
  // CPU
  const cpuModel = os.cpus()[0].model;

  // RAM
  const totalMem = os.totalmem();
  const freeMem  = os.freemem();

  // GPU
  const graphics = await si.graphics();
  const gpuInfo  = graphics.controllers[0] || {};
  const gpuModel = gpuInfo.model || 'unknown';
  const gpuVram  = gpuInfo.vram  || 0;

   // Récupère toutes les partitions montées
   const partitions = await si.fsSize();

   // Détermine la racine du dossier courant (ex. 'C:\\')
   const cwdRoot = path.parse(process.cwd()).root;
 
   // Cherche la partition correspondant à cette racine
   const current = partitions.find(p => p.mount === cwdRoot) || partitions[0];
 
   // Prépare l’objet disque courant
   const disk = {
     mount: current.mount,           // ex. 'C:\\'
     fs:    current.fs,              // ex. 'C:'
     size:  current.size,            // bytes
     used:  current.used             // bytes
   };
 
  
  return { cpuModel, totalMem, freeMem, gpuModel, gpuVram, disk };

});


app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
