#!/usr/bin/env python3
"""
Windsurf-compatible skill script template

This template provides a starting point for scripts that work well
in the Windsurf environment with proper error handling and path management.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Windsurf-specific configuration
WORKSPACE_ROOT = Path("/c/Users/hh/Desktop/brian/code")
WINDSURF_CONFIG_DIR = Path(".windsurf")


def ensure_workspace_bounds(file_path):
    """Ensure file operations stay within workspace boundaries"""
    resolved_path = Path(file_path).resolve()
    
    if not str(resolved_path).startswith(str(WORKSPACE_ROOT)):
        raise SecurityError(f"File operation outside workspace bounds: {file_path}")
    
    return resolved_path


def handle_windsurf_errors(func):
    """Decorator for Windsurf-specific error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            if ".windsurf" in str(e):
                print(f"Workspace boundary error: {e}")
                return None
            raise
        except PermissionError as e:
            print(f"Windows permission error: {e}")
            return None
        except subprocess.CalledProcessError as e:
            print(f"Command execution error: {e}")
            return None
    return wrapper


@handle_windsurf_errors
def execute_windsurf_command(command, cwd=None):
    """Execute command in Windsurf bash environment"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        
        if result.returncode != 0:
            print(f"Command failed: {command}")
            print(f"Error: {result.stderr}")
            return None
            
        return result.stdout.strip()
    
    except Exception as e:
        print(f"Command execution failed: {e}")
        return None


def load_session_state():
    """Load previous session state if available"""
    state_file = WORKSPACE_ROOT / WINDSURF_CONFIG_DIR / "session_state.json"
    
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    
    return {}


def save_session_state(state):
    """Save current state for session recovery"""
    state_file = WORKSPACE_ROOT / WINDSURF_CONFIG_DIR / "session_state.json"
    
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2))
        return True
    except IOError:
        return False


def validate_windsurf_environment():
    """Validate that we're running in Windsurf environment"""
    checks = [
        ("Workspace root", WORKSPACE_ROOT.exists()),
        ("Bash available", subprocess.run(["which", "bash"], capture_output=True).returncode == 0),
        ("Python available", subprocess.run(["python", "--version"], capture_output=True).returncode == 0),
    ]
    
    all_good = True
    for name, check in checks:
        if not check:
            print(f"❌ {name} failed")
            all_good = False
        else:
            print(f"✅ {name} OK")
    
    return all_good


def main():
    """Main function - customize this for your skill"""
    print("🌊 Windsurf Skill Script")
    print("=" * 40)
    
    # Validate environment
    if not validate_windsurf_environment():
        print("❌ Environment validation failed")
        return 1
    
    # Load session state
    state = load_session_state()
    print(f"📝 Loaded session state: {list(state.keys())}")
    
    # Your skill logic here
    print("🚀 Skill execution placeholder")
    
    # Save session state
    state["last_run"] = "success"
    if save_session_state(state):
        print("💾 Session state saved")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
