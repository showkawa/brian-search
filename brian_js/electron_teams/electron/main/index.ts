import { app, shell, BrowserWindow, BrowserView, ipcMain } from 'electron'
import { join } from 'path'

class App {
  private mainWindow: BrowserWindow | null = null
  private sidebarView: BrowserView | null = null
  private teamsView: BrowserView | null = null
  private loginWindow: BrowserWindow | null = null
  private readonly sidebarWidth = 200

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
      width: 1920,
      height: 1080,
      webPreferences: {
        preload: join(__dirname, '../preload/index.js'),
        contextIsolation: false,
        nodeIntegration: true
      }
    })

    this.mainWindow.on('ready-to-show', () => {
      this.mainWindow?.show()
    })

    this.mainWindow.webContents.on('will-navigate', (event, url) => {
      if (url.startsWith('about:')) {
        event.preventDefault();
      }
    });

    this.mainWindow.webContents.setWindowOpenHandler((details) => {
      shell.openExternal(details.url)
      return { action: 'deny' }
    })

    // Handle Teams view new window requests (for login popups)
    this.setupTeamsWindowHandler()

    this.setupViews()
    this.handleResize()
  }

  private setupViews(): void {
    if (!this.mainWindow) return

    // Create Teams view (main content)
    this.teamsView = new BrowserView({
      webPreferences: {
        contextIsolation: false,
        nodeIntegration: false, // Disable for security and Teams compatibility
        webSecurity: false, // Allow cross-origin requests
        allowRunningInsecureContent: true,
        experimentalFeatures: true,
        backgroundThrottling: false,
        partition: 'persist:teams', // Use persistent session for Teams
        sandbox: false
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

    // Configure Teams session for service workers and authentication
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

    // Set a more standard user agent for better authentication compatibility
    teamsSession.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
  
    // Configure session for better authentication support
    teamsSession.webRequest.onBeforeSendHeaders((details, callback) => {
      // Add necessary headers for Teams authentication
      details.requestHeaders['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
      details.requestHeaders['Accept-Language'] = 'en-US,en;q=0.5'
      details.requestHeaders['Cache-Control'] = 'no-cache'
      details.requestHeaders['Pragma'] = 'no-cache'
      
      // Ensure proper referrer for authentication requests
      if (details.url.includes('login.microsoftonline.com') || details.url.includes('oauth2')) {
        details.requestHeaders['Referer'] = 'https://teams.microsoft.com/'
        details.requestHeaders['Origin'] = 'https://teams.microsoft.com'
      }
      
      callback({ requestHeaders: details.requestHeaders })
    })
    
    // Handle cookie management for persistent login
    teamsSession.cookies.on('changed', (event, cookie, cause, removed) => {
      if (!removed && (cookie.domain?.includes('microsoft.com') || cookie.domain?.includes('microsoftonline.com'))) {
        console.log('Teams authentication cookie updated:', cookie.name)
      }
    })
    
    // Persist authentication cookies
    teamsSession.webRequest.onCompleted((details) => {
      if (details.url.includes('login.microsoftonline.com') && details.statusCode === 200) {
        console.log('Authentication request completed successfully')
      }
    })

    // Set up Teams window handler after view is created
    this.setupTeamsWindowHandler()

    // Load URLs
    this.teamsView.webContents.loadURL('https://teams.microsoft.com/v2/', {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    
    // Load sidebar (React app)
    const isDev = process.env.NODE_ENV === 'development'
    if (isDev && process.env['ELECTRON_RENDERER_URL']) {
      this.sidebarView.webContents.loadURL(process.env['ELECTRON_RENDERER_URL'])
    } else {
      this.sidebarView.webContents.loadFile(join(__dirname, '../renderer/index.html'))
    }

    // Handle Teams loading and error events
    this.teamsView.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
      console.log('Teams load failed:', { errorCode, errorDescription, validatedURL });
    });

    this.teamsView.webContents.on('did-finish-load', () => {
      console.log('Teams content loaded successfully');
      
      // Inject enhanced Teams compatibility script
      if (this.teamsView?.webContents) {
        this.teamsView.webContents.executeJavaScript(`
          // Enhanced Teams compatibility script
          console.log('Initializing Teams in Electron environment...');
          
          // Provide window management compatibility for Teams
          if (!window.electronAPI) {
            window.electronAPI = {
              platform: 'electron',
              version: '1.0.0',
              isElectron: true
            };
          }
          
          // Handle Teams window management issues
          const originalCreateElement = document.createElement;
          document.createElement = function(tagName) {
            const element = originalCreateElement.call(this, tagName);
            
            // Handle iframe creation for Teams popups
            if (tagName.toLowerCase() === 'iframe') {
              element.addEventListener('load', () => {
                console.log('Teams iframe loaded:', element.src);
              });
            }
            
            return element;
          };
          
          // Handle deeplink and navigation compatibility
          window.addEventListener('message', (event) => {
            if (event.data) {
              if (event.data.type === 'deeplink' || event.data.type === 'navigation') {
                console.log('Teams navigation handled:', event.data);
                // Prevent default handling that might cause window ID issues
                event.preventDefault();
              }
            }
          });
          
          // Override window.open for better popup handling
          const originalOpen = window.open;
          window.open = function(url, name, features) {
            console.log('Teams window.open:', { url, name, features });
            
            // Allow Teams internal operations and loading windows
            if (!url || url === 'about:blank' || url.startsWith('about:') || 
                url.includes('teams.microsoft.com') || name === 'popup' || 
                (features && features.includes('popup'))) {
              return originalOpen.call(this, url, name, features);
            }
            
            console.log('External popup blocked:', url);
            return null;
          };
          
          // Suppress common Teams errors that don't affect functionality
          const originalError = console.error;
          console.error = function(...args) {
            const message = args.join(' ');
            if (message.includes('missing_deeplink') || 
                message.includes('Window ID is invalid') ||
                message.includes('Could not get loading window') ||
                message.includes('400 (Bad Request)') ||
                message.includes('oauth2/v2.0/token')) {
              console.warn('Teams compatibility warning (suppressed):', message);
              return;
            }
            originalError.apply(console, args);
          };
          
          // Add authentication compatibility helpers
          if (!window.msTeamsAuthHelper) {
            window.msTeamsAuthHelper = {
              handleAuthError: function(error) {
                console.log('Auth error handled by Electron wrapper:', error);
                // Attempt to refresh authentication
                if (window.location.href.includes('teams.microsoft.com')) {
                  setTimeout(() => {
                    window.location.reload();
                  }, 2000);
                }
              }
            };
          }
          
          console.log('Teams Electron compatibility initialized successfully');
        `).catch(err => {
          console.log('Script injection error:', err.message);
        });
      }
      
      // Only open DevTools in development
      const isDev = process.env.NODE_ENV === 'development';
      if (isDev) {
        this.teamsView?.webContents.openDevTools({
          mode: 'right'
        });
      }
    })

    // Also open DevTools for sidebar in development
    if (isDev) {
      this.sidebarView.webContents.once('did-finish-load', () => {
        this.sidebarView?.webContents.openDevTools({
          mode: 'right'
        })
      })
    }

    this.updateViewBounds()
  }

  private setupTeamsWindowHandler(): void {
    // Set up window open handler for Teams view after it's created
    if (this.teamsView) {
      this.teamsView.webContents.setWindowOpenHandler((details) => {
        const url = details.url
        
        // Allow Teams internal windows (loading screens, popups, etc.)
        if (url.startsWith('about:') || 
            url === '' || 
            url.includes('teams.microsoft.com') ||
            url.includes('microsoft.com/teams') ||
            url.includes('microsoftteams://') ||
            details.frameName === 'popup' ||
            details.features.includes('popup=1')) {
          
          // Allow Teams internal windows to open normally
          return { 
            action: 'allow',
            overrideBrowserWindowOptions: {
              webPreferences: {
                contextIsolation: false,
                nodeIntegration: false,
                webSecurity: true,
                allowRunningInsecureContent: true
              }
            }
          }
        }
        
        // Check if this is a login-related URL
        if (url.includes('login.microsoftonline.com') || 
            url.includes('login.live.com') || 
            url.includes('account.microsoft.com') ||
            url.includes('oauth') ||
            url.includes('auth')) {
          
          // Create or focus existing login window
          this.createLoginWindow(url)
          return { action: 'deny' } // Prevent default new window
        }
        
        // For other external URLs, open in external browser
        shell.openExternal(url)
        return { action: 'deny' }
      })
    }
  }

  private createLoginWindow(url: string): BrowserWindow {
    // If login window already exists, focus it and return
    if (this.loginWindow && !this.loginWindow.isDestroyed()) {
      this.loginWindow.focus()
      return this.loginWindow
    }

    // Create new login window with enhanced authentication support
    this.loginWindow = new BrowserWindow({
      width: 500,
      height: 700,
      minWidth: 400,
      minHeight: 500,
      show: false,
      autoHideMenuBar: true,
      titleBarStyle: 'default',
      parent: this.mainWindow || undefined,
      modal: false,
      webPreferences: {
        contextIsolation: false,
        nodeIntegration: false,
        webSecurity: true,
        partition: 'persist:teams', // Use same session as main Teams view
        allowRunningInsecureContent: true
      }
    })

    // Load login URL with proper headers for authentication
    this.loginWindow.loadURL(url, {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      extraHeaders: 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8\nAccept-Language: en-US,en;q=0.5\n'
    })

    this.loginWindow.on('ready-to-show', () => {
      this.loginWindow?.show()
    })

    // Clean up reference when window is closed
    this.loginWindow.on('closed', () => {
      this.loginWindow = null
    })

    // Enhanced login success handling with cookie synchronization
    this.loginWindow.webContents.on('did-navigate', (event, navigationUrl) => {
      console.log('Login window navigated to:', navigationUrl)
      
      if (navigationUrl.includes('teams.microsoft.com') && !navigationUrl.includes('login')) {
        console.log('Login successful, synchronizing cookies...')
        
        this.syncAuthenticationCookies().then(() => {
          console.log('Cookies synchronized, reloading Teams view')
          this.teamsView?.webContents.reload()
          this.loginWindow?.close()
        }).catch((err: any) => {
          console.error('Cookie sync failed:', err)
          this.teamsView?.webContents.reload()
          this.loginWindow?.close()
        })
      }
    })

    return this.loginWindow
  }

  // Synchronize authentication cookies between login window and main Teams view
  private async syncAuthenticationCookies(): Promise<void> {
    try {
      const loginSession = this.loginWindow?.webContents.session
      const teamsSession = this.teamsView?.webContents.session
      
      if (!loginSession || !teamsSession) {
        throw new Error('Sessions not available for cookie sync')
      }
      
      // Get all Microsoft-related cookies from login session
      const cookies = await loginSession.cookies.get({
        domain: '.microsoft.com'
      })
      
      const msOnlineCookies = await loginSession.cookies.get({
        domain: '.microsoftonline.com'
      })
      
      const teamsCookies = await loginSession.cookies.get({
        domain: '.teams.microsoft.com'
      })
      
      // Combine all authentication cookies
      const allAuthCookies = [...cookies, ...msOnlineCookies, ...teamsCookies]
      
      // Set cookies in the main Teams session
      for (const cookie of allAuthCookies) {
        try {
          await teamsSession.cookies.set({
            url: `https://${cookie.domain}${cookie.path}`,
            name: cookie.name,
            value: cookie.value,
            domain: cookie.domain,
            path: cookie.path,
            secure: cookie.secure,
            httpOnly: cookie.httpOnly,
            expirationDate: cookie.expirationDate,
            sameSite: cookie.sameSite as any
          })
        } catch (err: any) {
          console.warn('Failed to sync cookie:', cookie.name, err.message)
        }
      }
      
      console.log(`Synchronized ${allAuthCookies.length} authentication cookies`)
    } catch (error: any) {
      console.error('Cookie synchronization failed:', error.message)
      throw error
    }
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