"""macOS permission checking for screen capture and accessibility.

Checks required permissions and provides guidance for users.
See Executable Spec Section 2.3 for requirements.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PermissionStatus:
    """Status of required macOS permissions.

    Attributes:
        screen_recording: True if screen recording is allowed
        accessibility: True if accessibility access is allowed
        guidance: User guidance text if any permission is missing
    """

    screen_recording: bool
    accessibility: bool
    guidance: Optional[str] = None

    @property
    def all_granted(self) -> bool:
        """Check if all required permissions are granted."""
        return self.screen_recording and self.accessibility

    @property
    def missing_permissions(self) -> list[str]:
        """List of missing permission names."""
        missing = []
        if not self.screen_recording:
            missing.append("屏幕录制 (Screen Recording)")
        if not self.accessibility:
            missing.append("辅助功能 (Accessibility)")
        return missing


def check_permissions() -> PermissionStatus:
    """Check macOS permissions for screen capture and input injection.

    Returns:
        PermissionStatus with current permission states and guidance.
    """
    screen_ok = False
    accessibility_ok = False

    try:
        # Import pyobjc frameworks
        from Quartz import CGPreflightScreenCaptureAccess
        from ApplicationServices import AXIsProcessTrustedWithOptions

        # Check screen recording permission
        # CGPreflightScreenCaptureAccess returns true if access is granted
        screen_ok = CGPreflightScreenCaptureAccess()

        # Check accessibility permission
        # Pass None to check without prompting
        accessibility_ok = AXIsProcessTrustedWithOptions(None)

    except ImportError:
        # pyobjc not installed - assume permissions are fine (will fail later if not)
        return PermissionStatus(
            screen_recording=True,
            accessibility=True,
            guidance=None,
        )
    except Exception:
        # Other error - be conservative
        pass

    # Build guidance if needed
    guidance = None
    if not screen_ok or not accessibility_ok:
        missing = []
        if not screen_ok:
            missing.append("屏幕录制")
        if not accessibility_ok:
            missing.append("辅助功能")

        guidance = (
            f"需要授权: {', '.join(missing)}\n\n"
            "请前往: 系统设置 → 隐私与安全性 → "
            f"{' / '.join(missing)}\n"
            "找到本应用并勾选启用。\n\n"
            "授权后可能需要重启应用。"
        )

    return PermissionStatus(
        screen_recording=screen_ok,
        accessibility=accessibility_ok,
        guidance=guidance,
    )


def request_screen_recording_permission() -> bool:
    """Request screen recording permission from the user.

    This will trigger the system permission dialog if not already granted.

    Returns:
        True if permission is now granted, False otherwise.
    """
    try:
        from Quartz import CGRequestScreenCaptureAccess

        return CGRequestScreenCaptureAccess()
    except ImportError:
        return False
    except Exception:
        return False


def request_accessibility_permission() -> bool:
    """Request accessibility permission from the user.

    This will open System Preferences to the Accessibility pane
    if not already granted.

    Returns:
        True if permission is now granted, False otherwise.
    """
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        from Foundation import NSDictionary

        # Request with prompt
        options = NSDictionary.dictionaryWithObject_forKey_(
            True, "AXTrustedCheckOptionPrompt"
        )
        return AXIsProcessTrustedWithOptions(options)
    except ImportError:
        return False
    except Exception:
        return False


