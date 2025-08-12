import { app, shell, BrowserWindow, BrowserView, ipcMain } from 'electron'
import { join } from 'path'

class App {
  private mainWindow: BrowserWindow | null = null
  private sidebarView: BrowserView | null = null
  private teamsView: BrowserView | null = null
  private readonly sidebarWidth = 300

  constructor() {
    this.init()
  }

  private init() {
    app.whenReady().then(() => {
      app.setAppUserModelId('com.electron.teams')
      
      this.setupIpcHandlers()
      this.createWindow()

      app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
          this.createWindow()
        }
      })
    })

    app.on('window-all-closed', () => {
      if (process.platform !== 'darwin') {
        app.quit()
      }
    })
  }

  private setupIpcHandlers() {
    // Window controls
    ipcMain.handle('window:minimize', () => {
      this.mainWindow?.minimize()
    })

    ipcMain.handle('window:maximize', () => {
      if (this.mainWindow?.isMaximized()) {
        this.mainWindow.unmaximize()
      } else {
        this.mainWindow?.maximize()
      }
    })

    ipcMain.handle('window:close', () => {
      this.mainWindow?.close()
    })

    // Teams controls
    ipcMain.handle('teams:reload', () => {
      this.teamsView?.webContents.reload()
    })

    ipcMain.handle('teams:toggle-devtools', () => {
      const webContents = this.teamsView?.webContents
      if (webContents) {
        if (webContents.isDevToolsOpened()) {
          webContents.closeDevTools()
        } else {
          webContents.openDevTools()
        }
      }
    })

    ipcMain.handle('teams:clear-cache', async () => {
      const session = this.teamsView?.webContents.session
      if (session) {
        await session.clearCache()
        this.teamsView?.webContents.reload()
      }
    })

    // App info
    ipcMain.handle('app:get-version', () => {
      return app.getVersion()
    })
  }

  private createWindow(): void {
    this.mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 1000,
      minHeight: 600,
      show: false,
      autoHideMenuBar: true,
      titleBarStyle: 'default',
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        sandbox: false,
        contextIsolation: false,
        nodeIntegration: true
      }
    })

    this.mainWindow.on('ready-to-show', () => {
      this.mainWindow?.show()
    })

    this.mainWindow.webContents.setWindowOpenHandler((details) => {
      shell.openExternal(details.url)
      return { action: 'deny' }
    })

    this.setupViews()
    this.handleResize()
  }

  private setupViews(): void {
    if (!this.mainWindow) return

    // Create Teams view (main content)
    this.teamsView = new BrowserView({
      webPreferences: {
        contextIsolation: false,
        nodeIntegration: true,
        webSecurity: false, // Allow cross-origin requests
        allowRunningInsecureContent: true,
        experimentalFeatures: true,
        backgroundThrottling: false
      }
    })

    // Create sidebar view (right menu)
    this.sidebarView = new BrowserView({
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        contextIsolation: false,
        nodeIntegration: true
      }
    })

    this.mainWindow.setBrowserView(this.teamsView)
    this.mainWindow.addBrowserView(this.sidebarView)

    // Configure Teams session for service workers
    const teamsSession = this.teamsView.webContents.session
    
    // Set permissions for service workers and notifications
    teamsSession.setPermissionRequestHandler((webContents, permission, callback) => {
      const allowedPermissions = [
        'notifications',
        'media',
        'geolocation',
        'microphone',
        'camera',
        'midi',
        'background-sync',
        'push-messaging'
      ]
      callback(allowedPermissions.includes(permission))
    })

    // Enable service worker support
    teamsSession.setUserAgent(teamsSession.getUserAgent() + ' ElectronTeams/1.0.0')

    // Load URLs
    this.teamsView.webContents.loadURL('https://teams.microsoft.com/v2/', {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 ElectronTeams/1.0.0'
    })
    
    // Load sidebar (React app)
    const isDev = process.env.NODE_ENV === 'development'
    if (isDev && process.env['ELECTRON_RENDERER_URL']) {
      this.sidebarView.webContents.loadURL(process.env['ELECTRON_RENDERER_URL'])
    } else {
      this.sidebarView.webContents.loadFile(join(__dirname, '../renderer/index.html'))
    }

    // Auto-open DevTools for Teams view when content is loaded
    this.teamsView.webContents.once('did-finish-load', () => {
      console.log('Teams content loaded, opening DevTools...')
      
      // Inject script to handle service worker errors gracefully
      if (this.teamsView?.webContents) {
        this.teamsView.webContents.executeJavaScript(`
          // Override console.error to catch service worker errors
          const originalError = console.error;
          console.error = function(...args) {
            const message = args.join(' ');
            if (message.includes('ServiceWorker') || message.includes('sw registration fail')) {
              console.warn('Service Worker registration disabled in Electron environment:', message);
              return;
            }
            originalError.apply(console, args);
          };
          
          // Disable service worker registration
          if ('serviceWorker' in navigator) {
            Object.defineProperty(navigator, 'serviceWorker', {
              value: undefined,
              writable: false
            });
          }
          
          console.log('Teams loaded in Electron environment - Service Workers disabled');
        `).catch(err => {
          console.log('Script injection error (normal):', err.message);
        });
      }
      
      this.teamsView?.webContents.openDevTools({
        mode: 'detach' // Opens in separate window
      })
    })

    // Also open DevTools for sidebar in development
    if (isDev) {
      this.sidebarView.webContents.once('did-finish-load', () => {
        this.sidebarView?.webContents.openDevTools({
          mode: 'detach'
        })
      })
    }

    this.updateViewBounds()
  }

  private handleResize(): void {
    this.mainWindow?.on('resized', () => {
      this.updateViewBounds()
    })
  }

  private updateViewBounds(): void {
    if (!this.mainWindow || !this.teamsView || !this.sidebarView) return

    const { width, height } = this.mainWindow.getContentBounds()
    
    // Teams view takes up the left portion
    this.teamsView.setBounds({
      x: 0,
      y: 0,
      width: width - this.sidebarWidth,
      height: height
    })

    // Sidebar view takes up the right portion
    this.sidebarView.setBounds({
      x: width - this.sidebarWidth,
      y: 0,
      width: this.sidebarWidth,
      height: height
    })
  }
}

new App()