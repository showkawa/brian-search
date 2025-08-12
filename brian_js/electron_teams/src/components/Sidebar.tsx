import React from 'react'
import { Button } from '@/components/ui/button'
import { RefreshCw, Wrench, Trash2, Info, Settings } from 'lucide-react'

export function Sidebar() {
  const handleReloadTeams = () => {
    if (window.electronAPI) {
      window.electronAPI.reloadTeams()
    }
  }

  const handleToggleDevTools = () => {
    if (window.electronAPI) {
      window.electronAPI.toggleDevTools()
    }
  }

  const handleClearCache = () => {
    if (window.electronAPI) {
      window.electronAPI.clearCache()
    }
  }

  const handleGetVersion = async () => {
    if (window.electronAPI) {
      const version = await window.electronAPI.getVersion()
      alert(`App Version: ${version}`)
    }
  }

  const menuItems = [
    {
      title: 'Reload Teams',
      description: 'Refresh the Teams interface',
      icon: RefreshCw,
      action: handleReloadTeams,
      variant: 'default' as const
    },
    {
      title: 'Developer Tools',
      description: 'Toggle Teams DevTools',
      icon: Wrench,
      action: handleToggleDevTools,
      variant: 'outline' as const
    },
    {
      title: 'Clear Cache',
      description: 'Clear Teams cache and reload',
      icon: Trash2,
      action: handleClearCache,
      variant: 'destructive' as const
    },
    {
      title: 'App Info',
      description: 'Show application information',
      icon: Info,
      action: handleGetVersion,
      variant: 'ghost' as const
    }
  ]

  return (
    <div className="h-full w-full bg-background border-l border-border flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center space-x-2">
          <Settings className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-semibold text-foreground">Teams Control</h1>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your Teams experience
        </p>
      </div>

      {/* Menu Items */}
      <div className="flex-1 p-4 space-y-3">
        {menuItems.map((item, index) => {
          const Icon = item.icon
          return (
            <div key={index} className="space-y-2">
              <Button
                variant={item.variant}
                className="w-full justify-start text-left h-auto p-3"
                onClick={item.action}
              >
                <div className="flex items-start space-x-3">
                  <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 space-y-1">
                    <div className="font-medium">{item.title}</div>
                    <div className="text-xs opacity-80">{item.description}</div>
                  </div>
                </div>
              </Button>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <div className="text-xs text-muted-foreground text-center">
          Electron Teams Wrapper
        </div>
      </div>
    </div>
  )
}