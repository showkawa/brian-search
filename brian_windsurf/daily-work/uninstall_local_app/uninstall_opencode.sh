#!/bin/bash

# OpenCode Uninstall Script
# This script removes OpenCode application from Windows system

OPencode_DIR="/c/Users/hh/AppData/Local/OpenCode"
OPencode_DATA_DIR="/c/Users/hh/AppData/Local/ai.opencode.desktop"
UNINSTALLER="/c/Users/hh/AppData/Local/OpenCode/uninstall.exe"

echo "=== OpenCode Uninstall Script ==="
echo "Starting uninstallation process..."

# Check if OpenCode directory exists
if [ ! -d "$OPencode_DIR" ]; then
    echo "OpenCode directory not found at $OPencode_DIR"
    exit 1
fi

echo "Found OpenCode installation at: $OPencode_DIR"

# Kill any running OpenCode processes
echo "Terminating any running OpenCode processes..."
taskkill //F //IM OpenCode.exe 2>/dev/null || echo "No OpenCode processes found"
taskkill //F //IM opencode-cli.exe 2>/dev/null || echo "No opencode-cli processes found"

# Check if uninstaller exists
if [ -f "$UNINSTALLER" ]; then
    echo "Running official uninstaller..."
    # Run the official uninstaller silently
    "$UNINSTALLER" //S
    
    # Wait for uninstaller to complete
    sleep 10
    
    # Check if directory still exists
    if [ -d "$OPencode_DIR" ]; then
        echo "Uninstaller completed, but directory still exists"
        echo "Performing manual cleanup..."
    fi
fi

# Remove the main OpenCode directory
echo "Removing OpenCode directory..."
rm -rf "$OPencode_DIR"

if [ $? -eq 0 ]; then
    echo "OpenCode directory removed successfully"
else
    echo "Failed to remove OpenCode directory"
    exit 1
fi

# Remove the OpenCode data directory
if [ -d "$OPencode_DATA_DIR" ]; then
    echo "Removing OpenCode data directory..."
    rm -rf "$OPencode_DATA_DIR"
    
    if [ $? -eq 0 ]; then
        echo "OpenCode data directory removed successfully"
    else
        echo "Failed to remove OpenCode data directory"
    fi
fi

# Clean up desktop shortcuts
echo "Cleaning up desktop shortcuts..."
DESKTOP="/c/Users/hh/Desktop"
if [ -f "$DESKTOP/OpenCode.lnk" ]; then
    rm "$DESKTOP/OpenCode.lnk"
    echo "Removed desktop shortcut"
fi

# Clean up Start Menu shortcuts
echo "Cleaning up Start Menu shortcuts..."
STARTMENU="/c/Users/hh/AppData/Roaming/Microsoft/Windows/Start Menu/Programs"
if [ -f "$STARTMENU/OpenCode.lnk" ]; then
    rm "$STARTMENU/OpenCode.lnk"
    echo "Removed Start Menu shortcut"
fi

# Clean up roaming AppData
echo "Cleaning up roaming AppData..."
APPDATA_ROAMING="/c/Users/hh/AppData/Roaming"
if [ -d "$APPDATA_ROAMING/OpenCode" ]; then
    rm -rf "$APPDATA_ROAMING/OpenCode"
    echo "Removed roaming AppData files"
fi

echo ""
echo "=== Uninstall Complete ==="
echo "OpenCode has been removed from your system"
echo ""
echo "Please restart your computer to complete the removal process"
