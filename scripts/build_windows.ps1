# QueueSend Windows Build Script
# Builds a standalone .exe using PyInstaller
#
# Usage: .\scripts\build_windows.ps1
# Prerequisites: Python 3.11+, pip

param(
    [switch]$Clean,
    [switch]$OneFile,
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  QueueSend Windows Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to project root
Set-Location $ProjectRoot
Write-Host "[1/6] Working directory: $ProjectRoot" -ForegroundColor Green

# Clean previous builds if requested
if ($Clean) {
    Write-Host "[2/6] Cleaning previous builds..." -ForegroundColor Yellow
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "*.spec") { Remove-Item -Force "*.spec" }
} else {
    Write-Host "[2/6] Skipping clean (use -Clean to clean)" -ForegroundColor Gray
}

# Check Python version
Write-Host "[3/6] Checking Python version..." -ForegroundColor Green
$pythonVersion = python --version 2>&1
Write-Host "  Found: $pythonVersion"

$versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
if ($versionMatch) {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
        Write-Host "ERROR: Python 3.11+ required, found $pythonVersion" -ForegroundColor Red
        exit 1
    }
}

# Install/upgrade PyInstaller
Write-Host "[4/6] Installing PyInstaller..." -ForegroundColor Green
pip install --upgrade pyinstaller | Out-Null

# Install project dependencies
Write-Host "[5/6] Installing project dependencies..." -ForegroundColor Green
pip install -r requirements.lock | Out-Null

# Build with PyInstaller
Write-Host "[6/6] Building with PyInstaller..." -ForegroundColor Green

$pyinstallerArgs = @(
    "--name=QueueSend",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--distpath=$OutputDir",
    "--add-data=app/assets;app/assets",
    "--hidden-import=pynput.keyboard._win32",
    "--hidden-import=pynput.mouse._win32",
    "--collect-all=PySide6",
    "app/main.py"
)

if ($OneFile) {
    $pyinstallerArgs += "--onefile"
    Write-Host "  Mode: Single executable (--onefile)" -ForegroundColor Cyan
} else {
    $pyinstallerArgs += "--onedir"
    Write-Host "  Mode: Directory bundle (--onedir)" -ForegroundColor Cyan
}

# Run PyInstaller
python -m PyInstaller @pyinstallerArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Build Successful!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    
    if ($OneFile) {
        $outputPath = Join-Path $OutputDir "QueueSend.exe"
    } else {
        $outputPath = Join-Path $OutputDir "QueueSend"
    }
    
    Write-Host "Output: $outputPath" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To test on a clean system:" -ForegroundColor Yellow
    Write-Host "  1. Copy the output to a Windows machine without Python" -ForegroundColor White
    Write-Host "  2. Run QueueSend.exe" -ForegroundColor White
    Write-Host "  3. Complete calibration and send a test message" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "Build FAILED!" -ForegroundColor Red
    exit 1
}

