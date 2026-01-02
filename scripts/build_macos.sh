#!/bin/bash
# QueueSend macOS Build Script
# Builds a standalone .app bundle using PyInstaller
#
# Usage: ./scripts/build_macos.sh
# Prerequisites: Python 3.11+, pip, Xcode Command Line Tools

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${1:-dist}"

echo "========================================"
echo "  QueueSend macOS Build Script"
echo "========================================"
echo ""

cd "$PROJECT_ROOT"
echo "[1/7] Working directory: $PROJECT_ROOT"

# Parse arguments
CLEAN=false
ONEFILE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean) CLEAN=true; shift ;;
        --onefile) ONEFILE=true; shift ;;
        *) shift ;;
    esac
done

# Clean previous builds if requested
if [ "$CLEAN" = true ]; then
    echo "[2/7] Cleaning previous builds..."
    rm -rf build dist *.spec
else
    echo "[2/7] Skipping clean (use --clean to clean)"
fi

# Check Python version
echo "[3/7] Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1)
echo "  Found: $PYTHON_VERSION"

MAJOR=$(echo "$PYTHON_VERSION" | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]); then
    echo "ERROR: Python 3.11+ required, found $PYTHON_VERSION"
    exit 1
fi

# Install/upgrade PyInstaller
echo "[4/7] Installing PyInstaller..."
pip3 install --upgrade pyinstaller > /dev/null

# Install project dependencies
echo "[5/7] Installing project dependencies..."
pip3 install -r requirements.lock > /dev/null

# Install macOS-specific dependencies
echo "[6/7] Installing macOS dependencies (pyobjc)..."
pip3 install pyobjc-framework-Quartz pyobjc-framework-ApplicationServices > /dev/null

# Build with PyInstaller
echo "[7/7] Building with PyInstaller..."

PYINSTALLER_ARGS=(
    "--name=QueueSend"
    "--windowed"
    "--noconfirm"
    "--clean"
    "--distpath=$OUTPUT_DIR"
    "--add-data=app/assets:app/assets"
    "--hidden-import=pynput.keyboard._darwin"
    "--hidden-import=pynput.mouse._darwin"
    "--collect-all=PySide6"
    "--osx-bundle-identifier=com.queuesend.app"
    "app/main.py"
)

if [ "$ONEFILE" = true ]; then
    PYINSTALLER_ARGS+=("--onefile")
    echo "  Mode: Single executable (--onefile)"
else
    PYINSTALLER_ARGS+=("--onedir")
    echo "  Mode: App bundle (--onedir)"
fi

python3 -m PyInstaller "${PYINSTALLER_ARGS[@]}"

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "  Build Successful!"
    echo "========================================"
    echo ""
    
    OUTPUT_PATH="$OUTPUT_DIR/QueueSend.app"
    echo "Output: $OUTPUT_PATH"
    echo ""
    echo "IMPORTANT: macOS Permissions Required"
    echo "--------------------------------------"
    echo "Before running, grant these permissions in System Settings:"
    echo ""
    echo "  1. Privacy & Security → Screen Recording → Add QueueSend"
    echo "  2. Privacy & Security → Accessibility → Add QueueSend"
    echo ""
    echo "Note: Only single display is supported on macOS."
    echo ""
    echo "To test on a clean system:"
    echo "  1. Copy QueueSend.app to /Applications"
    echo "  2. Right-click → Open (first time to bypass Gatekeeper)"
    echo "  3. Grant required permissions"
    echo "  4. Restart the app after granting permissions"
    echo "  5. Complete calibration and send a test message"
else
    echo ""
    echo "Build FAILED!"
    exit 1
fi

