# Windsurf Integration Patterns

This document provides patterns and best practices for integrating skills with Windsurf's specific features and environment.

## File System Patterns

### Absolute Path Usage
```python
# Good - Use absolute paths
skill_path = Path("/c/Users/hh/project/skills/my-skill")
config_file = Path("/c/Users/hh/project/config.json")

# Avoid - Relative paths may break
skill_path = Path("./skills/my-skill")  # Not recommended
```

### Path Handling for Windows/Git Bash
```python
import os
from pathlib import Path

# Use os.path.join() for cross-platform compatibility
config_path = os.path.join("C:", "Users", "hh", "config.json")

# Or use Path with proper handling
data_dir = Path("C:/Users/hh/data")
```

## Command Execution Patterns

### Windsurf Bash Commands
```python
# Use bash-compatible commands
command = "ls -la /c/Users/hh/Desktop"
# Avoid Windows CMD specific commands
# command = "dir C:\\Users\\hh\\Desktop"  # Not recommended
```

### Tool Availability Checks
```python
def check_windsurf_tools():
    """Verify that required tools are available in Windsurf"""
    try:
        # Test basic commands
        subprocess.run(["ls", "/"], check=True, capture_output=True)
        subprocess.run(["python", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
```

## Memory System Integration

### Session Recovery Patterns
```python
# Design skills to recover state
def load_session_state():
    """Load previous session state if available"""
    state_file = Path("/c/Users/hh/project/.windsurf/session_state.json")
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {}

def save_session_state(state):
    """Save current state for session recovery"""
    state_file = Path("/c/Users/hh/project/.windsurf/session_state.json")
    state_file.write_text(json.dumps(state))
```

### Context Window Management
```python
# Optimize content for Windsurf's context handling
def get_relevant_content(query, max_tokens=2000):
    """Get content optimized for context window"""
    # Implement progressive disclosure
    if is_simple_query(query):
        return get_basic_content()
    else:
        return get_detailed_content(max_tokens)
```

## MCP Server Integration

### MCP Server Patterns
```python
# Skills that work with MCP servers
def use_mcp_server(server_name, operation):
    """Pattern for using MCP servers in Windsurf"""
    try:
        # Check if server is available
        if server_name in available_mcp_servers():
            return execute_mcp_operation(server_name, operation)
        else:
            return fallback_operation(operation)
    except Exception as e:
        log_error(f"MCP server {server_name} unavailable: {e}")
        return fallback_operation(operation)
```

## Workspace Management

### Project Structure Alignment
```
project-root/
├── .windsurf/
│   ├── skills/           # Custom skills
│   ├── workspace.json     # Workspace configuration
│   └── session_state.json # Session recovery data
├── src/                   # Source code
├── docs/                  # Documentation
└── scripts/               # Utility scripts
```

### Development Workflow Integration
```python
# Support Windsurf's iterative development
def test_in_windsurf_environment():
    """Test skill functionality in actual Windsurf environment"""
    # Test file operations
    test_file_operations()
    
    # Test command execution
    test_command_execution()
    
    # Test tool integration
    test_mcp_integration()
    
    return True
```

## Error Handling Patterns

### Windsurf-Specific Error Handling
```python
def handle_windsurf_errors(func):
    """Decorator for Windsurf-specific error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            # Handle file system boundary issues
            if ".windsurf" in str(e):
                return handle_workspace_boundary_error(e)
            raise
        except PermissionError as e:
            # Handle Windows permission issues
            return handle_windows_permission_error(e)
        except subprocess.CalledProcessError as e:
            # Handle command execution failures
            return handle_command_error(e)
    return wrapper
```

## Testing Patterns

### Windsurf Environment Testing
```python
def test_windsurf_compatibility():
    """Test suite for Windsurf compatibility"""
    tests = [
        test_absolute_path_handling,
        test_bash_command_execution,
        test_memory_system_integration,
        test_mcp_server_compatibility,
        test_session_recovery,
    ]
    
    results = []
    for test in tests:
        try:
            test()
            results.append((test.__name__, "PASS"))
        except Exception as e:
            results.append((test.__name__, f"FAIL: {e}"))
    
    return results
```

## Performance Optimization

### Context Optimization
```python
# Optimize for Windsurf's context window
def optimize_content_for_context(content, priority="high"):
    """Optimize content based on priority for context management"""
    if priority == "high":
        return content[:1000]  # Keep essential content
    elif priority == "medium":
        return content[:2000]  # Keep important content
    else:
        return content[:5000]  # Keep detailed content
```

## Security Considerations

### Workspace Boundary Respect
```python
def ensure_workspace_bounds(file_path):
    """Ensure file operations stay within workspace boundaries"""
    workspace_root = Path("/c/Users/hhh/Desktop/brian/code")
    resolved_path = Path(file_path).resolve()
    
    if not str(resolved_path).startswith(str(workspace_root)):
        raise SecurityError("File operation outside workspace bounds")
    
    return resolved_path
```

These patterns help ensure that skills work seamlessly within Windsurf's environment and take advantage of its specific features.
