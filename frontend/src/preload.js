// See the Electron documentation for details on how to use preload scripts:
// https://www.electronjs.org/docs/latest/tutorial/process-model#preload-scripts

const { contextBridge, ipcRenderer, webUtils, shell } = require('electron');


contextBridge.exposeInMainWorld('electron', {
  // Vérifie si l'API est exposée
  openDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
  getFilePath: (file) => {
    if (webUtils?.getPathForFile) {
      const path = webUtils.getPathForFile(file);
      console.log('webUtils.getPathForFile returned:', path);
      return path;
    }
    
    console.log('Falling back to file.path:', file.path);
    return file.path;
  },
  onBackendEvent: (handler) => {
    const listener = (_e, payload) => handler(payload);
    ipcRenderer.on('backend-event', listener);
    return () => ipcRenderer.removeListener('backend-event', listener);
  },
  onBackendLog: (handler) => {
    const listener = (_e, msg) => handler(msg);
    ipcRenderer.on('backend-log', listener);
    return () => ipcRenderer.removeListener('backend-log', listener);
  },
  onBackendLogError: (handler) => {
    const listener = (_e, msg) => handler(msg);
    ipcRenderer.on('backend-log-error', listener);
    return () => ipcRenderer.removeListener('backend-log-error', listener);
  },
  restartBackend: () => ipcRenderer.invoke('backend:restart'),
  getBackendStatus: () => ipcRenderer.invoke('backend:getStatus'),
  isPackaged: () => ipcRenderer.invoke('app:isPackaged'),
  openExternal: (url) => shell.openExternal(url)
});