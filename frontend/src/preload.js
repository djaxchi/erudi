// See the Electron documentation for details on how to use preload scripts:
// https://www.electronjs.org/docs/latest/tutorial/process-model#preload-scripts


const { contextBridge, ipcRenderer } = require('electron');

// Vérifie si preload.js est bien chargé
console.log("Le script preload.js est chargé");

contextBridge.exposeInMainWorld('electron', {
  // Vérifie si l'API est exposée
  openDirectory: () => {
    return ipcRenderer.invoke('dialog:openDirectory');
  }
});

