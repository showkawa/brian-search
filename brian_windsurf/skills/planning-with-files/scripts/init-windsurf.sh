#!/bin/bash

# Planning with Files - Windsurf Initialization Script
# This script initializes the three core planning files for Windsurf

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/../templates"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Planning with Files - Windsurf Initialization${NC}"
echo

# Check if we're in a valid project directory
if [ ! -d ".git" ] && [ ! -f "package.json" ] && [ ! -f "README.md" ]; then
    echo -e "${YELLOW}⚠️  Warning: Not in a typical project directory${NC}"
    echo -e "${YELLOW}   Make sure you're in the right project folder${NC}"
    echo
fi

# Function to copy template if file doesn't exist
copy_template() {
    local template_file="$1"
    local target_file="$2"
    local description="$3"
    
    if [ -f "$target_file" ]; then
        echo -e "${YELLOW}⚠️  $target_file already exists - skipping${NC}"
    else
        if [ -f "$template_file" ]; then
            cp "$template_file" "$target_file"
            echo -e "${GREEN}✅ Created $description${NC}"
        else
            echo -e "${RED}❌ Template $template_file not found${NC}"
            return 1
        fi
    fi
}

# Copy the three core planning files
copy_template "$TEMPLATES_DIR/task_plan.md" "task_plan.md" "Task Plan (task_plan.md)"
copy_template "$TEMPLATES_DIR/findings.md" "findings.md" "Findings Log (findings.md)"
copy_template "$TEMPLATES_DIR/progress.md" "progress.md" "Progress Log (progress.md)"

echo
echo -e "${GREEN}🎉 Planning files initialized successfully!${NC}"
echo
echo -e "${BLUE}📋 Next steps:${NC}"
echo "1. Edit task_plan.md to set your goal and phases"
echo "2. Start working, updating files as you progress"
echo "3. Use the 5-Question Reboot Test to stay on track"
echo
echo -e "${BLUE}💡 Remember:${NC}"
echo "- Update task_plan.md after each phase"
echo "- Save findings to findings.md after discoveries"
echo "- Log progress in progress.md throughout the session"
echo
echo -e "${GREEN}Happy planning! 🚀${NC}"
