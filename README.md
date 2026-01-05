# QueueSend

**跨平台 ROI 变化驱动自动化工具** | Cross-platform ROI Change-Driven Automation Tool

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PySide6](https://img.shields.io/badge/UI-PySide6-green.svg)](https://doc.qt.io/qtforpython-6/)

QueueSend is a desktop automation tool that sends messages one-by-one by monitoring screen region (ROI) changes. It uses visual change detection to determine when each message has been successfully sent before proceeding to the next.

## Features

- **Visual Change Detection**: Monitors a screen region (ROI) to detect when messages are sent
- **Batch Message Sending**: Queues multiple messages and sends them sequentially
- **Cross-Platform**: Works on Windows and macOS (single display)
- **Calibration System**: Easy point-and-click calibration for input field, send button, and ROI
- **Pause/Resume/Stop Controls**: Full control over automation with state preservation
- **Rectangle & Circle ROI**: Choose the detection shape that works best for your use case

## System Requirements

| Requirement | Windows | macOS |
|-------------|---------|-------|
| OS Version | Windows 10/11 | macOS 13+ |
| Python | 3.11+ | 3.11+ |
| Display | Single or Multi-monitor | **Single display only** |
| DPI Scaling | 100% recommended | N/A |

### macOS Limitations

⚠️ **macOS currently only supports single display configurations.** Multi-monitor setups are not supported.

## Installation

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/your-org/QueueSend.git
cd QueueSend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.lock

# macOS only: Install additional dependencies
pip install pyobjc-framework-Quartz pyobjc-framework-ApplicationServices

# Run the application
python -m app.main
```

### Pre-built Executables

Download the latest release from the [Releases](https://github.com/your-org/QueueSend/releases) page:

- **Windows**: `QueueSend.exe` (standalone executable)
- **macOS**: `QueueSend.app` (application bundle)

## Quick Start

### 1. Calibration

Before using QueueSend, you must calibrate three points:

1. **Input Point**: Where to click to focus the message input field
2. **Send Button**: Where to click to send the message
3. **ROI (Region of Interest)**: The screen area to monitor for changes after sending

### 2. Enter Messages

- Enter your messages in the message list (one per entry)
- Press **Enter** to add a new line within a message
- Empty entries are automatically filtered out

### 3. Start Automation

1. Click **Start** to begin
2. A 2-second countdown gives you time to prepare
3. The tool will:
   - Click the input point
   - Paste the message
   - Click the send button
   - Wait for ROI changes (2 consecutive detections required)
   - Proceed to the next message

### 4. Controls

- **Pause**: Freezes the automation, preserving current state
- **Resume**: Continues from where it paused
- **Stop**: Immediately stops and returns to idle state

## Platform-Specific Setup

### Windows DPI Settings

For accurate click positioning, **100% display scaling is recommended**.

If you must use higher scaling:

1. The app attempts to set DPI awareness automatically
2. If a yellow warning banner appears, coordinates may be offset
3. Consider running at 100% scaling for best results

To check/change scaling:
- Right-click Desktop → Display settings → Scale and layout

### macOS Permissions

QueueSend requires two permissions to function:

#### Screen Recording Permission
Required for capturing the ROI to detect changes.

1. Open **System Settings** → **Privacy & Security** → **Screen Recording**
2. Click the **+** button
3. Navigate to and add **QueueSend.app**
4. Restart QueueSend

#### Accessibility Permission
Required for clicking and keyboard input.

1. Open **System Settings** → **Privacy & Security** → **Accessibility**
2. Click the **+** button
3. Navigate to and add **QueueSend.app**
4. Restart QueueSend

> **Note**: After granting permissions, you must restart the application for changes to take effect.

## Building from Source

### Windows

```powershell
# Run the build script
.\scripts\build_windows.ps1

# For a single .exe file:
.\scripts\build_windows.ps1 -OneFile

# Clean build:
.\scripts\build_windows.ps1 -Clean
```

Output: `dist/QueueSend/` or `dist/QueueSend.exe`

### macOS

```bash
# Make script executable
chmod +x scripts/build_macos.sh

# Run the build script
./scripts/build_macos.sh

# For clean build:
./scripts/build_macos.sh --clean
```

Output: `dist/QueueSend.app`

## Running Tests

```bash
# Install test dependencies
pip install pytest

# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_diff.py -v
```

## Usage Tips

### ROI Selection Best Practices

Choose an ROI that shows **clear changes after sending**:

✅ **Good ROI choices:**
- Chat message list area (new message appears)
- Send button state changes (enabled/disabled/loading)
- Delivery confirmation indicators

❌ **Avoid these ROI choices:**
- Animated areas (causes false positives)
- Static areas (causes infinite waiting)
- Areas with constant updates (timestamps, clocks)

### Threshold Calibration

The detection threshold (`TH_HOLD`) determines sensitivity:

1. Click **Calibrate** after setting up ROI
2. The tool samples static noise and recommends a threshold
3. Default: `0.02` (2% average pixel change)
4. Lower = more sensitive, Higher = less sensitive

### Message Formatting

- **Newlines**: Press Enter to add newlines within a message
- **Multi-line**: Full multi-line messages are supported
- **Empty entries**: Automatically filtered when starting

## Troubleshooting

### macOS: "Screen Recording permission not granted"

1. Ensure QueueSend is added to Screen Recording permissions
2. **Restart the application** after granting permission
3. If still not working, remove and re-add the permission

### macOS: Clicks not registering

1. Ensure QueueSend is added to Accessibility permissions
2. **Restart the application** after granting permission
3. Some applications may block automated input

### Windows: Click positions are offset

1. Check display scaling (100% recommended)
2. Look for yellow DPI warning banner in the app
3. If warning appears, try:
   - Running at 100% scaling
   - Restarting the application
   - Running as administrator

### Infinite waiting / Detection not progressing

1. **Check ROI selection**: Ensure ROI shows visible changes after sending
2. **Lower threshold**: Try reducing `TH_HOLD` value
3. **Use calibration**: Click Calibrate to get recommended threshold
4. **Verify target app**: Ensure the target application is visible and not minimized

### Paste not working / Newlines lost

1. Some applications may not support Ctrl+V/Cmd+V pasting
2. Rich text editors may strip newlines
3. Try the target application's paste behavior manually first

### Multi-monitor issues (Windows)

- Ensure all monitors are at the same DPI scaling
- Negative coordinates are supported for left-positioned monitors
- ROI and click points must be within virtual desktop bounds

## Architecture

```
app/
├── main.py              # Application entry point
├── controller.py        # UI-to-engine coordinator
├── core/
│   ├── engine.py        # State machine & automation loop
│   ├── capture.py       # Screen capture (mss)
│   ├── diff.py          # Change detection algorithm
│   ├── model.py         # Data structures
│   ├── constants.py     # Configuration constants
│   ├── logging.py       # Thread-safe logging
│   └── os_adapter/      # Platform-specific code
│       ├── win_dpi.py      # Windows DPI handling
│       ├── mac_permissions.py  # macOS permission checks
│       ├── input_inject.py     # Click/paste operations
│       └── validation.py       # Coordinate validation
└── ui/
    ├── main_window.py       # Main application window
    ├── run_panel.py         # Running status panel
    ├── calibration_overlay.py  # ROI/point selection
    ├── message_editor.py    # Message list editor
    └── widgets.py           # Reusable UI components
```

## Constants Reference

| Constant | Value | Description |
|----------|-------|-------------|
| `T_COUNTDOWN_SEC` | 2.0 | Countdown before starting |
| `T_COOL_SEC` | 1.0 | Cooldown after each send |
| `SAMPLE_HZ` | 1.0 | ROI sampling rate (1 FPS) |
| `HOLD_HITS_REQUIRED` | 2 | Consecutive hits to confirm change |
| `TH_HOLD_DEFAULT` | 0.02 | Default detection threshold |
| `CAPTURE_RETRY_N` | 3 | Screenshot retry attempts |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Security & Privacy

- **No data collection**: All processing is local
- **No network access**: Screenshots never leave your machine
- **Permissions**: Required only for screen capture and input automation
- **Logs**: May contain message content for debugging (stored locally)

---

**Note**: This tool is designed for legitimate automation purposes. Please use responsibly and in accordance with the terms of service of any applications you automate.


