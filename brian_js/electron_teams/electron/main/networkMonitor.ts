import { session, WebContents } from 'electron'

// 网络请求类型定义
export interface NetworkRequest {
  id: string
  url: string
  method: string
  headers: Record<string, string | string[]>
  timestamp: number
  type: 'http' | 'streaming' | 'sse' | 'websocket'
  status?: number
  responseHeaders?: Record<string, string | string[]>
  body?: string
  responseBody?: string
  duration?: number
}

// 网络监控事件类型
export interface NetworkMonitorEvents {
  'request-started': (request: NetworkRequest) => void
  'request-completed': (request: NetworkRequest) => void
  'request-failed': (request: NetworkRequest, error: string) => void
  'streaming-data': (request: NetworkRequest, chunk: string) => void
  'sse-message': (request: NetworkRequest, data: any) => void
}

// 网络监控器类
export class NetworkMonitor {
  private requests: Map<string, NetworkRequest> = new Map()
  private listeners: Map<keyof NetworkMonitorEvents, Function[]> = new Map()
  private isMonitoring: boolean = false
  private sessionInstance: Electron.Session | null = null

  constructor() {
    this.initializeEventMaps()
  }

  private initializeEventMaps() {
    const events: (keyof NetworkMonitorEvents)[] = [
      'request-started',
      'request-completed', 
      'request-failed',
      'streaming-data',
      'sse-message'
    ]
    
    events.forEach(event => {
      this.listeners.set(event, [])
    })
  }

  // 开始监控指定session的网络请求
  public startMonitoring(sessionName: string = 'persist:teams'): void {
    if (this.isMonitoring) {
      console.log('Network monitoring is already active')
      return
    }

    this.sessionInstance = session.fromPartition(sessionName)
    if (!this.sessionInstance) {
      console.error('Failed to get session for monitoring')
      return
    }

    this.setupRequestInterception()
    this.setupResponseInterception()
    this.isMonitoring = true
    
    console.log(`Network monitoring started for session: ${sessionName}`)
  }

  // 停止监控
  public stopMonitoring(): void {
    if (!this.isMonitoring || !this.sessionInstance) {
      return
    }

    // 清理拦截器
    this.sessionInstance.webRequest.onBeforeRequest(null)
    this.sessionInstance.webRequest.onBeforeSendHeaders(null)
    this.sessionInstance.webRequest.onHeadersReceived(null)
    this.sessionInstance.webRequest.onResponseStarted(null)
    this.sessionInstance.webRequest.onCompleted(null)
    this.sessionInstance.webRequest.onErrorOccurred(null)

    this.isMonitoring = false
    this.requests.clear()
    console.log('Network monitoring stopped')
  }

  // 设置请求拦截
  private setupRequestInterception(): void {
    if (!this.sessionInstance) return

    // 拦截请求开始
    this.sessionInstance.webRequest.onBeforeRequest((details, callback) => {
      const request: NetworkRequest = {
        id: details.id.toString(),
        url: details.url,
        method: details.method,
        headers: {},
        timestamp: Date.now(),
        type: this.determineRequestType(details.url, details.method),
        body: details.uploadData ? this.extractUploadData(details.uploadData) : undefined
      }

      this.requests.set(request.id, request)
      this.emit('request-started', request)

      // 处理Teams信号API冲突
      if (details.url.includes('sigsapi') && details.url.includes('/Signals')) {
        console.log('🔄 Teams Signals API request detected:', details.url)
        
        // 检查是否有重复的信号请求
        const duplicateRequests = Array.from(this.requests.values()).filter(req => 
          req.url.includes('sigsapi') && 
          req.url.includes('/Signals') && 
          req.id !== request.id &&
          Date.now() - req.timestamp < 5000 // 5秒内的重复请求
        )
        
        if (duplicateRequests.length > 0) {
          console.warn('⚠️ Duplicate Signals API request detected, may cause 409 conflict')
        }
      }

      // 处理OAuth2认证请求
      if (details.url.includes('oauth2/v2.0/token')) {
        console.log('🔐 OAuth2 token request detected:', details.url)
        
        // 检查是否是Copilot相关的认证请求
        if (details.url.includes('client-request-id')) {
          console.log('🤖 Copilot authentication request detected')
        }
        
        // 记录请求体信息用于调试
        if (details.uploadData && details.uploadData.length > 0) {
          const bodyData = this.extractUploadData(details.uploadData)
          if (bodyData.includes('scope')) {
            console.log('🔍 OAuth2 scopes requested:', bodyData.match(/scope=([^&]*)/)?.[1] || 'unknown')
          }
        }
      }

      // 记录特殊请求类型
      if (request.type === 'sse') {
        console.log('🔄 SSE Request detected:', request.url)
      } else if (request.type === 'streaming') {
        console.log('📡 Streaming Request detected:', request.url)
      }

      callback({})
    })

    // 拦截请求头
    this.sessionInstance.webRequest.onBeforeSendHeaders((details, callback) => {
      const request = this.requests.get(details.id.toString())
      if (request) {
        request.headers = details.requestHeaders || {}
        
        // 检测SSE请求特征
        const accept = request.headers['Accept'] || request.headers['accept']
        const acceptValue = Array.isArray(accept) ? accept[0] : accept
        if (acceptValue?.includes('text/event-stream')) {
          request.type = 'sse'
        }
      }

      callback({ requestHeaders: details.requestHeaders })
    })
  }

  // 设置响应拦截
  private setupResponseInterception(): void {
    if (!this.sessionInstance) return

    // 拦截响应头
    this.sessionInstance.webRequest.onHeadersReceived((details, callback) => {
      const request = this.requests.get(details.id.toString())
      if (request) {
        request.status = details.statusCode
        request.responseHeaders = details.responseHeaders || {}

        // 检测流式响应
        const contentType = this.getHeaderValue(details.responseHeaders, 'content-type')
        if (contentType) {
          if (contentType.includes('text/event-stream')) {
            request.type = 'sse'
          } else if (contentType.includes('application/stream') || 
                    contentType.includes('text/stream')) {
            request.type = 'streaming'
          }
        }
      }

      callback({ responseHeaders: details.responseHeaders })
    })

    // 拦截响应开始
    this.sessionInstance.webRequest.onResponseStarted((details) => {
      const request = this.requests.get(details.id.toString())
      if (request) {
        request.status = details.statusCode
        request.responseHeaders = details.responseHeaders || {}
      }
    })

    // 拦截请求完成
    this.sessionInstance.webRequest.onCompleted((details) => {
      const request = this.requests.get(details.id.toString())
      if (request) {
        request.status = details.statusCode
        request.duration = Date.now() - request.timestamp
        
        this.emit('request-completed', request)
        
        // 清理已完成的请求（保留最近1000个）
        if (this.requests.size > 1000) {
          const oldestKey = this.requests.keys().next().value
          if (oldestKey) {
            this.requests.delete(oldestKey)
          }
        }
      }
    })

    // 拦截请求错误
    this.sessionInstance.webRequest.onErrorOccurred((details) => {
      const request = this.requests.get(details.id.toString())
      if (request) {
        request.duration = Date.now() - request.timestamp
        this.emit('request-failed', request, details.error)
        this.requests.delete(details.id.toString())
      }
    })
  }

  // 确定请求类型
  private determineRequestType(url: string, method: string): NetworkRequest['type'] {
    // SSE通常使用GET方法且URL包含特定模式
    if (method === 'POST' && (
      url.includes('/events') || 
      url.includes('/stream') || 
      url.includes('/sse') ||
      url.includes('text/event-stream')
    )) {
      return 'sse'
    }

    // WebSocket升级请求
    if (url.startsWith('ws://') || url.startsWith('wss://')) {
      return 'websocket'
    }

    // 流式请求通常包含stream关键字
    if (url.includes('/stream') || url.includes('streaming')) {
      return 'streaming'
    }

    return 'http'
  }

  // 提取上传数据
  private extractUploadData(uploadData: Electron.UploadData[]): string {
    try {
      return uploadData.map(data => {
        if (data.bytes) {
          return data.bytes.toString('utf8')
        }
        return ''
      }).join('')
    } catch (error) {
      return ''
    }
  }

  // 获取响应头值
  private getHeaderValue(headers: Record<string, string | string[]> | undefined, key: string): string | undefined {
    if (!headers) return undefined
    
    const value = headers[key] || headers[key.toLowerCase()]
    return Array.isArray(value) ? value[0] : value
  }

  // 事件监听器
  public on<K extends keyof NetworkMonitorEvents>(
    event: K, 
    listener: NetworkMonitorEvents[K]
  ): void {
    const listeners = this.listeners.get(event)
    if (listeners) {
      listeners.push(listener)
    }
  }

  // 移除事件监听器
  public off<K extends keyof NetworkMonitorEvents>(
    event: K, 
    listener: NetworkMonitorEvents[K]
  ): void {
    const listeners = this.listeners.get(event)
    if (listeners) {
      const index = listeners.indexOf(listener)
      if (index > -1) {
        listeners.splice(index, 1)
      }
    }
  }

  // 触发事件
  private emit<K extends keyof NetworkMonitorEvents>(
    event: K, 
    ...args: Parameters<NetworkMonitorEvents[K]>
  ): void {
    const listeners = this.listeners.get(event)
    if (listeners) {
      listeners.forEach(listener => {
        try {
          (listener as any)(...args)
        } catch (error) {
          console.error(`Error in network monitor listener for ${event}:`, error)
        }
      })
    }
  }

  // 获取所有活跃请求
  public getActiveRequests(): NetworkRequest[] {
    return Array.from(this.requests.values())
  }

  // 获取特定类型的请求
  public getRequestsByType(type: NetworkRequest['type']): NetworkRequest[] {
    return Array.from(this.requests.values()).filter(req => req.type === type)
  }

  // 搜索请求
  public searchRequests(pattern: string): NetworkRequest[] {
    const regex = new RegExp(pattern, 'i')
    return Array.from(this.requests.values()).filter(req => 
      regex.test(req.url) || 
      regex.test(req.method) ||
      (req.body && regex.test(req.body))
    )
  }

  // 获取统计信息
  public getStats(): {
    total: number
    byType: Record<NetworkRequest['type'], number>
    byStatus: Record<number, number>
  } {
    const requests = Array.from(this.requests.values())
    const stats = {
      total: requests.length,
      byType: { http: 0, streaming: 0, sse: 0, websocket: 0 },
      byStatus: {} as Record<number, number>
    }

    requests.forEach(req => {
      stats.byType[req.type]++
      if (req.status) {
        stats.byStatus[req.status] = (stats.byStatus[req.status] || 0) + 1
      }
    })

    return stats
  }

  // 导出请求数据
  public exportRequests(filter?: {
    type?: NetworkRequest['type']
    status?: number
    urlPattern?: string
  }): NetworkRequest[] {
    let requests = Array.from(this.requests.values())

    if (filter) {
      if (filter.type) {
        requests = requests.filter(req => req.type === filter.type)
      }
      if (filter.status) {
        requests = requests.filter(req => req.status === filter.status)
      }
      if (filter.urlPattern) {
        const regex = new RegExp(filter.urlPattern, 'i')
        requests = requests.filter(req => regex.test(req.url))
      }
    }

    return requests
  }
}

// 创建全局网络监控实例
export const networkMonitor = new NetworkMonitor()

// 便捷的监控函数
export function startNetworkMonitoring(sessionName?: string): void {
  networkMonitor.startMonitoring(sessionName)
}

export function stopNetworkMonitoring(): void {
  networkMonitor.stopMonitoring()
}

// 预定义的监控器设置
export function setupTeamsNetworkMonitoring(): void {
  networkMonitor.startMonitoring('persist:teams')

  // 监听Teams相关的网络请求
  networkMonitor.on('request-started', (request) => {
    if (request.url.includes('teams.microsoft.com')) {
      console.log(`🌐 Teams Request: ${request.method} ${request.url}`)
    }
  })

  // 监听SSE连接
  networkMonitor.on('request-started', (request) => {
    if (request.type === 'sse') {
      console.log(`📡 SSE Connection: ${request.url}`)
    }
  })

  // 监听流式请求
  networkMonitor.on('request-started', (request) => {
    if (request.type === 'streaming') {
      console.log(`🔄 Streaming Request: ${request.url}`)
    }
  })

  // 监听请求完成
  networkMonitor.on('request-completed', (request) => {
    if (request.duration && request.duration > 5000) { // 超过5秒的请求
      console.log(`⏱️ Slow Request: ${request.method} ${request.url} (${request.duration}ms)`)
    }
  })

  // 监听请求失败
  networkMonitor.on('request-failed', (request, error) => {
    console.log(`❌ Request Failed: ${request.method} ${request.url} - ${error}`)
  })
}
