"""Start and configure the Windows Live Captions application."""

import ctypes
import shutil
import subprocess
import time
from typing import Optional, Sequence

import uiautomation as auto

from function.config import AUTO_ENABLE_MICROPHONE, LIVE_CAPTIONS_START_TIMEOUT


LIVE_CAPTIONS_WINDOW_CLASS = "LiveCaptionsDesktopWindow"
UIA_SEARCH_TIMEOUT = 0.5

# A stale WinUI/XAML element should fail quickly so the capture loop can
# reacquire it instead of freezing the dashboard for uiautomation's default
# ten-second timeout.
auto.SetGlobalSearchTimeout(UIA_SEARCH_TIMEOUT)


def get_live_captions_window():
    """Return the Live Captions window control, whether it exists or not."""
    desktop = auto.GetRootControl()
    return desktop.Control(
        searchDepth=1,
        ClassName=LIVE_CAPTIONS_WINDOW_CLASS,
    )


def lc_detect(timeout: float = 0.2) -> bool:
    """Check whether Windows Live Captions is currently open."""
    try:
        if get_live_captions_window().Exists(timeout):
            print("Live Captions Found")
            return True
    except Exception as exc:
        print(f"Live Captions detection failed: {str(exc)[:80]}")

    print("Live Captions Not Found")
    return False


def launch_live_captions_with_powershell() -> bool:
    """Launch Live Captions with its official Win+Ctrl+L shortcut via PowerShell."""
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        print("PowerShell was not found")
        return False

    script = """
$source = @'
using System;
using System.Runtime.InteropServices;

public static class SaveLiveCaptionsKeyboard
{
    [DllImport("user32.dll")]
    public static extern void keybd_event(
        byte virtualKey,
        byte scanCode,
        uint flags,
        UIntPtr extraInfo);
}
'@

Add-Type -TypeDefinition $source
$keyUp = 0x0002
[SaveLiveCaptionsKeyboard]::keybd_event(0x5B, 0, 0, [UIntPtr]::Zero)
[SaveLiveCaptionsKeyboard]::keybd_event(0x11, 0, 0, [UIntPtr]::Zero)
[SaveLiveCaptionsKeyboard]::keybd_event(0x4C, 0, 0, [UIntPtr]::Zero)
[SaveLiveCaptionsKeyboard]::keybd_event(0x4C, 0, $keyUp, [UIntPtr]::Zero)
[SaveLiveCaptionsKeyboard]::keybd_event(0x11, 0, $keyUp, [UIntPtr]::Zero)
[SaveLiveCaptionsKeyboard]::keybd_event(0x5B, 0, $keyUp, [UIntPtr]::Zero)
"""

    try:
        subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                script,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        print("Requested Windows Live Captions startup through PowerShell")
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Unable to launch Windows Live Captions: {exc}")
        return False


def _find_control(
    root,
    automation_ids: Sequence[str],
    names: Sequence[str],
    timeout: float = 0.08,
):
    for automation_id in automation_ids:
        control = root.Control(searchDepth=8, AutomationId=automation_id)
        if control.Exists(timeout):
            return control

    for name in names:
        control = root.Control(searchDepth=8, Name=name)
        if control.Exists(timeout):
            return control

    return None


def _wait_for_control(
    root,
    automation_ids: Sequence[str],
    names: Sequence[str],
    timeout: float = 2.0,
):
    """Return as soon as a XAML control becomes available."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        control = _find_control(root, automation_ids, names)
        if control is not None:
            return control
        time.sleep(0.05)
    return None


def _activate_control(control, prefer_expand: bool = False) -> bool:
    """Activate a UIA control without animating or moving the mouse pointer."""
    if prefer_expand:
        expand_pattern = control.GetPattern(auto.PatternId.ExpandCollapsePattern)
        if expand_pattern is not None:
            return bool(expand_pattern.Expand(waitTime=0))

    invoke_pattern = control.GetPattern(auto.PatternId.InvokePattern)
    if invoke_pattern is not None:
        return bool(invoke_pattern.Invoke(waitTime=0))

    # Compatibility fallback for Windows builds that do not expose a usable
    # UIA action pattern. This clicks instantly rather than animating the mouse.
    control.Click(simulateMove=False, waitTime=0)
    return True


def enable_microphone_audio(captions_window) -> bool:
    """Best-effort enablement of the Live Captions microphone menu item."""
    try:
        settings = _wait_for_control(
            captions_window,
            ("SettingsButton",),
            ("Settings", "设置"),
        )
        if settings is None:
            print("Live Captions settings button was not found")
            return False

        if not _activate_control(settings):
            print("Live Captions settings button could not be invoked")
            return False

        preferences = _wait_for_control(
            captions_window,
            ("PreferencesButton", "CaptionOptionsMenuFlyoutSubItem"),
            ("Preferences", "首选项", "偏好设置"),
        )
        if preferences is not None:
            if not _activate_control(preferences, prefer_expand=True):
                print("Live Captions preferences menu could not be opened")
                return False

        microphone = _wait_for_control(
            captions_window,
            ("MicrophoneMenuFlyoutItem",),
            (
                "Include microphone audio",
                "包含麦克风音频",
                "包括麦克风音频",
            ),
        )
        if microphone is None:
            print("Live Captions microphone option was not found")
            return False

        toggle_pattern = microphone.GetPattern(auto.PatternId.TogglePattern)
        if toggle_pattern is not None:
            if toggle_pattern.ToggleState == auto.ToggleState.On:
                return True
            toggle_pattern.Toggle(waitTime=0)
            time.sleep(0.05)
            return toggle_pattern.ToggleState == auto.ToggleState.On

        # Some Windows builds expose this as a checked menu item without a
        # TogglePattern. It starts off after every Live Captions launch, so a
        # single click enables it.
        return _activate_control(microphone)
    except Exception as exc:
        print(f"Unable to enable microphone audio automatically: {exc}")
        return False


def ensure_live_captions(
    timeout: float = LIVE_CAPTIONS_START_TIMEOUT,
) -> tuple[bool, Optional[bool]]:
    """Ensure Live Captions is open.

    Returns ``(is_ready, microphone_enabled)``. ``microphone_enabled`` is
    ``None`` when this process did not start Live Captions or automatic
    microphone enablement is disabled.
    """
    if lc_detect():
        return True, None

    if not launch_live_captions_with_powershell():
        return False, None

    deadline = time.monotonic() + timeout
    captions_window = None
    while time.monotonic() < deadline:
        try:
            candidate = get_live_captions_window()
            if candidate.Exists(UIA_SEARCH_TIMEOUT):
                captions_window = candidate
                break
        except Exception:
            pass
        time.sleep(0.25)

    if captions_window is None:
        return False, None

    if not AUTO_ENABLE_MICROPHONE:
        return True, None

    return True, enable_microphone_audio(captions_window)


def close_live_captions(timeout: float = 2.0) -> bool:
    """Ask Windows Live Captions to close and briefly wait for completion."""
    try:
        captions_window = get_live_captions_window()
        if not captions_window.Exists(0.1):
            return True

        closed = False
        window_pattern = captions_window.GetPattern(auto.PatternId.WindowPattern)
        if window_pattern is not None:
            closed = bool(window_pattern.Close(waitTime=0))

        if not closed:
            window_handle = captions_window.NativeWindowHandle
            if window_handle:
                # WM_CLOSE requests a normal application shutdown.
                closed = bool(ctypes.windll.user32.PostMessageW(window_handle, 0x0010, 0, 0))

        if not closed:
            print("Unable to request Windows Live Captions shutdown")
            return False

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if not get_live_captions_window().Exists(0.08):
                    print("Windows Live Captions closed")
                    return True
            except Exception:
                return True
            time.sleep(0.05)

        print("Windows Live Captions did not close within the timeout")
        return False
    except Exception as exc:
        print(f"Unable to close Windows Live Captions: {exc}")
        return False
