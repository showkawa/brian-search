export interface ElectronAPI {
  platform: string
  minimize: () => Promise<void>
  maximize: () => Promise<void>
  close: () => Promise<void>
  reloadTeams: () => Promise<void>
  toggleDevTools: () => Promise<void>
  clearCache: () => Promise<void>
  getVersion: () => Promise<string>
  onWindowFocus: (callback: () => void) => () => void
  onWindowBlur: (callback: () => void) => () => void
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}