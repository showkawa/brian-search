# Windsurf Skill Template

## Overview

[TODO: 1-2 sentences explaining what this skill enables]

## Windsurf Integration

This skill is optimized for Windsurf environment with the following features:

- **File System Compatibility**: Uses absolute paths and respects workspace boundaries
- **Session Recovery**: Maintains state across Windsurf sessions
- **Command Integration**: Works with Windsurf's bash environment
- **Error Handling**: Handles Windows/Git Bash specific issues

## Quick Start

1. **Initialize the skill**:
   ```bash
   scripts/init_skill.py my-windsurf-skill --path skills/public --resources scripts,references
   ```

2. **Customize the scripts** using the Windsurf template in `assets/windsurf-templates/`

3. **Test in Windsurf environment** before packaging

## Usage Examples

### Basic Usage
```bash
# Use the skill with Windsurf-optimized commands
python scripts/my_script.py --input /c/Users/hh/project/data
```

### Advanced Usage
```bash
# With session recovery
python scripts/my_script.py --resume-session --workspace /c/Users/hh/project
```

## File Structure

```
my-windsurf-skill/
├── SKILL.md                    # Main skill documentation
├── scripts/                    # Windsurf-compatible scripts
│   ├── main.py                # Main skill logic
│   └── utils.py               # Utility functions
├── references/                 # Documentation and patterns
│   └── windsurf-patterns.md   # Windsurf integration guide
└── assets/                     # Templates and resources
    └── windsurf-templates/     # Windsurf-specific templates
        └── skill_script_template.py
```

## Development Notes

### Path Handling
- Always use absolute paths starting with `/c/Users/hh/`
- Use `Path` from pathlib for cross-platform compatibility
- Respect workspace boundaries in file operations

### Command Execution
- Test commands in Windsurf's bash environment
- Use the provided error handling decorator
- Check tool availability before execution

### Session Management
- Use `load_session_state()` and `save_session_state()` for persistence
- Store state in `.windsurf/session_state.json`
- Handle session recovery gracefully

## Troubleshooting

### Common Issues

**File not found errors**:
- Verify absolute paths are correct
- Check workspace boundary permissions
- Ensure files exist in expected locations

**Command execution failures**:
- Test commands manually in Windsurf bash
- Check tool availability with `which command`
- Use proper Windows path formats

**Session state issues**:
- Verify `.windsurf/` directory exists
- Check JSON formatting in session state
- Ensure write permissions for state file

### Getting Help

1. Check `references/windsurf-patterns.md` for integration patterns
2. Use the template in `assets/windsurf-templates/` as starting point
3. Test in actual Windsurf environment before distribution
4. Validate with `scripts/quick_validate.py`

## Best Practices

- ✅ Use absolute paths for all file operations
- ✅ Test scripts in actual Windsurf environment
- ✅ Handle Windows/Git Bash compatibility
- ✅ Implement proper error handling
- ✅ Support session recovery
- ✅ Validate before packaging

- ❌ Assume cross-platform compatibility without testing
- ❌ Use relative paths that may break
- ❌ Ignore Windows-specific issues
- ❌ Forget session recovery design
