// See the Electron documentation for details on how to use preload scripts:
// https://www.electronjs.org/docs/latest/tutorial/process-model#preload-scripts

const { contextBridge, ipcRenderer, webUtils } = require('electron');

// Vérifie si preload.js est bien chargé
console.log("Le script preload.js est chargé");

contextBridge.exposeInMainWorld('electron', {
  // Vérifie si l'API est exposée
  openDirectory: () => {
    return ipcRenderer.invoke('dialog:openDirectory');
  }, 
  getFilePath: (file) => {
    if (webUtils?.getPathForFile) {
      const path = webUtils.getPathForFile(file);
      console.log('webUtils.getPathForFile returned:', path);
      return path;
    }
    
    console.log('Falling back to file.path:', file.path);
    return file.path;
  }
});

// Expose additional API for data management
contextBridge.exposeInMainWorld('electronAPI', {
  openDataFolder: () => ipcRenderer.invoke('data:openFolder'),
  clearAllData: () => ipcRenderer.invoke('data:clearAll')
});

