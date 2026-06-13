# Planning with Files for Windsurf

A Windsurf-optimized version of the Manus-style persistent markdown planning skill that transforms your workflow to use persistent files for planning, progress tracking, and knowledge storage.

## 🚀 Quick Start

### Installation

The skill is already installed in your Windsurf skills directory at:
```
C:\Users\hh\.codeium\windsurf\skills\planning-with-files\
```

### Initialize a New Project

1. Navigate to your project directory
2. Run the initialization script:

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\hh\.codeium\windsurf\skills\planning-with-files\scripts\init-windsurf.ps1"
```

**Linux/macOS/Git Bash:**
```bash
bash "C:\Users\hh\.codeium\windsurf\skills\planning-with-files\scripts\init-windsurf.sh"
```

3. Edit `task_plan.md` to set your goal and phases
4. Start working with the planning workflow!

## 📋 The Three-File System

| File | Purpose | When to Update |
|------|---------|----------------|
| `task_plan.md` | Your roadmap with phases and progress | After each phase completion |
| `findings.md` | Research storage and discoveries | After any discovery or research |
| `progress.md` | Session log and test results | Throughout your work session |

## 🎯 Core Principles

### 1. Context Window = RAM, Filesystem = Disk
```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

### 2. The 2-Action Rule
After every 2 view/browser/search operations, IMMEDIATELY save key findings to text files. This prevents visual information from being lost.

### 3. Read Before Decide
Before major decisions, read your plan file to keep goals fresh in your attention window.

### 4. Update After Act
After completing any phase:
- Mark phase status: `in_progress` → `complete`
- Log any errors encountered
- Note files created/modified

## 🔄 Session Recovery

When your context window fills up, simply read the three planning files to recover your state:
1. `task_plan.md` → "Where am I?" and "Where am I going?"
2. `findings.md` → "What have I learned?"
3. `progress.md` → "What have I done?"

## ❌ Anti-Patterns to Avoid

| Don't | Do Instead |
|-------|------------|
| Start executing immediately | Create plan file FIRST |
| Stuff everything in context | Store large content in files |
| Hide errors and retry silently | Log errors to plan file |
| Repeat failed actions | Track attempts, mutate approach |
| Create files in skills directory | Create files in your project |

## 🎯 When to Use This Pattern

**Use for:**
- Multi-step tasks (3+ steps)
- Research projects
- Building/creating projects
- Tasks spanning many tool calls
- Anything requiring organization

**Skip for:**
- Simple questions
- Single-file edits
- Quick lookups

## 📚 Templates Reference

The skill includes three templates in the `templates/` directory:

- `task_plan.md` - Phase tracking with goals, decisions, and error logs
- `findings.md` - Research storage with requirements, findings, and resources
- `progress.md` - Session logging with test results and detailed progress

## 🔧 Windsurf Integration

This skill is specifically optimized for Windsurf:
- ✅ Compatible with Windsurf's file system access
- ✅ Works with Windsurf's command structure
- ✅ Integrates with Windsurf's memory system
- ✅ Supports Windsurf's workspace management
- ✅ Uses Windows-compatible paths and scripts

## 🎉 Success Metrics

You're using the pattern correctly when you can answer the 5-Question Reboot Test:

| Question | Answer Source |
|----------|---------------|
| Where am I? | Current phase in task_plan.md |
| Where am I going? | Remaining phases |
| What's the goal? | Goal statement in plan |
| What have I learned? | findings.md |
| What have I done? | progress.md |

## 🤝 Contributing

This is a Windsurf-optimized fork of the original [planning-with-files](https://github.com/OthmanAdi/planning-with-files) skill by OthmanAdi.

## 📄 License

Same license as the original project.

---

**Happy planning with Windsurf! 🚀**
