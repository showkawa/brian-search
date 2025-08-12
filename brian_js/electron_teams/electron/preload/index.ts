import { contextBridge, ipcRenderer } from 'electron'

// Custom APIs for renderer
const electronAPI = {
  platform: process.platform,
  
  // Window controls
  minimize: () => ipcRenderer.invoke('window:minimize'),
  maximize: () => ipcRenderer.invoke('window:maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  
  // Teams controls
  reloadTeams: () => ipcRenderer.invoke('teams:reload'),
  toggleDevTools: () => ipcRenderer.invoke('teams:toggle-devtools'),
  clearCache: () => ipcRenderer.invoke('teams:clear-cache'),
  
  // App info
  getVersion: () => ipcRenderer.invoke('app:get-version'),
  
  // Event listeners
  onWindowFocus: (callback: () => void) => {
    ipcRenderer.on('window:focus', callback)
    return () => ipcRenderer.removeListener('window:focus', callback)
  },
  
  onWindowBlur: (callback: () => void) => {
    ipcRenderer.on('window:blur', callback)
    return () => ipcRenderer.removeListener('window:blur', callback)
  }
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electronAPI', electronAPI)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electronAPI = electronAPI
}

export type ElectronAPI = typeof electronAPI