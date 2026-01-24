# Planning with Files - PowerShell Initialization Script for Windsurf
# This script initializes the three core planning files for Windsurf

param(
    [switch]$Force,
    [switch]$Help
)

if ($Help) {
    Write-Host "Planning with Files - Windsurf Initialization" -ForegroundColor Blue
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\init-windsurf.ps1          # Initialize planning files"
    Write-Host "  .\init-windsurf.ps1 -Force   # Overwrite existing files"
    Write-Host "  .\init-windsurf.ps1 -Help   # Show this help"
    exit 0
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TemplatesDir = Join-Path $ScriptDir "..\templates"

Write-Host "🚀 Planning with Files - Windsurf Initialization" -ForegroundColor Blue
Write-Host ""

# Check if we're in a valid project directory
if (-not (Test-Path ".git") -and -not (Test-Path "package.json") -and -not (Test-Path "README.md")) {
    Write-Host "⚠️  Warning: Not in a typical project directory" -ForegroundColor Yellow
    Write-Host "   Make sure you're in the right project folder" -ForegroundColor Yellow
    Write-Host ""
}

# Function to copy template
function Copy-Template {
    param(
        [string]$TemplateFile,
        [string]$TargetFile,
        [string]$Description
    )
    
    if ((Test-Path $TargetFile) -and -not $Force) {
        Write-Host "⚠️  $TargetFile already exists - skipping (use -Force to overwrite)" -ForegroundColor Yellow
    } else {
        if (Test-Path $TemplateFile) {
            Copy-Item $TemplateFile $TargetFile -Force
            Write-Host "✅ Created $Description" -ForegroundColor Green
        } else {
            Write-Host "❌ Template $TemplateFile not found" -ForegroundColor Red
            return $false
        }
    }
    return $true
}

# Copy the three core planning files
$success = $true
$success = $success -and (Copy-Template "$TemplatesDir\task_plan.md" "task_plan.md" "Task Plan (task_plan.md)")
$success = $success -and (Copy-Template "$TemplatesDir\findings.md" "findings.md" "Findings Log (findings.md)")
$success = $success -and (Copy-Template "$TemplatesDir\progress.md" "progress.md" "Progress Log (progress.md)")

Write-Host ""
if ($success) {
    Write-Host "🎉 Planning files initialized successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Some files failed to initialize" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📋 Next steps:" -ForegroundColor Blue
Write-Host "1. Edit task_plan.md to set your goal and phases"
Write-Host "2. Start working, updating files as you progress"
Write-Host "3. Use the 5-Question Reboot Test to stay on track"
Write-Host ""
Write-Host "💡 Remember:" -ForegroundColor Blue
Write-Host "- Update task_plan.md after each phase"
Write-Host "- Save findings to findings.md after discoveries"
Write-Host "- Log progress in progress.md throughout the session"
Write-Host ""
Write-Host "Happy planning! 🚀" -ForegroundColor Green
