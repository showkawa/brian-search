# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is an Electron application that wraps Microsoft Teams with a custom sidebar menu. It uses a dual-view architecture where the main window contains two BrowserViews: a sidebar for navigation/controls and the main Teams interface.

## Development Commands
- `pnpm dev` - Start development server with hot reload
- `pnpm build` - Build the application for production
- `pnpm lint` - Run ESLint with auto-fix
- `pnpm format` - Format code with Prettier
- `pnpm start` - Preview the built application

## Build Commands
- `pnpm build:win` - Build for Windows
- `pnpm build:mac` - Build for macOS  
- `pnpm build:linux` - Build for Linux

## Special Development Setup
This project uses a custom Electron binary setup. For development:
1. Download Electron binary from https://github.com/electron/electron/releases
2. Use `cross-env ELECTRON_OVERRIDE_DIST_PATH=<path-to-electron-binary> pnpm dev`
3. Install dependencies with `cross-env ELECTRON_SKIP_BINARY_DOWNLOAD=1 pnpm install`

## Architecture

### Electron Main Process
- `electron/main/index.ts` - Main process entry point that creates the application window with dual BrowserViews
- Creates a 300px wide sidebar view and main Teams view
- Sidebar loads the React application, Teams view loads `https://teams.microsoft.com/v2/`
- Handles window resizing and view bounds management
- Implements IPC handlers for Teams control (reload, DevTools, cache clearing)
- Auto-opens DevTools for Teams view when content loads
- Disables Service Worker registration via JavaScript injection to prevent Teams SW errors

### React Renderer Process  
- `src/main.tsx` - React application entry point using React Router with hash routing
- `src/pages/index.tsx` - Sidebar component with menu items (Reload Teams, Toggle DevTools, Clear Cache)
- Uses file-based routing via `vite-plugin-pages` with pages in `src/pages/`

### Key Technologies
- **Electron + Vite** - Main framework using electron-vite for build process
- **React 18** - UI framework with TypeScript
- **Tailwind CSS** - Styling with shadcn/ui components
- **File-based routing** - Pages automatically routed from `src/pages/` directory
- **State Management** - Zustand for client state
- **Data Fetching** - SWR with ky for HTTP requests

### Build Configuration
- `electron.vite.config.ts` - Configures separate builds for main, preload, and renderer processes
- Uses path alias `@` pointing to `src/` directory
- Custom root configuration with index.html at project root instead of src/

### Project Structure
```
electron/          # Electron processes
├── main/          # Main process code
└── preload/       # Preload scripts
src/               # React renderer code
├── pages/         # File-based routes
├── lib/           # Utilities
└── main.tsx       # App entry point
```

## Teams Integration Specifics

### Service Worker Handling
The application disables Teams Service Worker registration to prevent errors in the Electron environment:
- Sets `webSecurity: false` for Teams BrowserView
- Injects JavaScript to override `navigator.serviceWorker`
- Suppresses Service Worker related console errors

### IPC Communication
Main process exposes these handlers via preload script:
- `teams:reload` - Reloads Teams content
- `teams:toggle-devtools` - Opens/closes DevTools for Teams view
- `teams:clear-cache` - Clears Teams session cache and reloads
- `app:get-version` - Returns application version

### Window Management
- Main window: 1400x900 (minimum 1000x600)
- Teams view: Left portion (width - 300px)
- Sidebar view: Right portion (300px wide)
- Auto-resizing bounds management on window resize

The application creates a Teams wrapper with an integrated sidebar for additional functionality while keeping the main Teams interface intact.