#!/usr/bin/env python3
"""
Phone Launcher - Connect to phone and launch scrcpy
"""

import sys
import subprocess
import threading
import time
from pathlib import Path
from phone_connector import PhoneConnector

# Platform-specific paths
if sys.platform == 'win32':
    SCRCPY_PATH = Path(__file__).parent / "scrcpy-win64-v3.3.3" / "scrcpy.exe"
    ADB_PATH = Path(__file__).parent / "scrcpy-win64-v3.3.3" / "adb.exe"
else:
    SCRCPY_PATH = "scrcpy"  # Use system scrcpy on Linux/macOS
    ADB_PATH = "adb"  # Use system adb on Linux/macOS

def keep_screen_off():
    """Monitor and keep phone screen off"""
    while True:
        time.sleep(2)
        # Check if screen is on
        result = subprocess.run(
            f"{ADB_PATH} shell dumpsys power | grep mWakefulness",
            capture_output=True,
            text=True,
            shell=True
        )

        if "Awake" in result.stdout or "mWakefulness=" not in result.stdout:
            # Screen is on or unknown state, turn it off
            subprocess.run(
                [ADB_PATH, "shell", "input", "keyevent", "KEYCODE_POWER"],
                capture_output=True
            )
            time.sleep(0.5)
            # Turn it off again to ensure it's off
            subprocess.run(
                [ADB_PATH, "shell", "input", "keyevent", "KEYCODE_POWER"],
                capture_output=True
            )

def main():
    # Connect to phone
    connector = PhoneConnector()

    if not connector.connect():
        print("\nPress Enter to exit...")
        input()
        return 1

    # Launch scrcpy with built-in screen-off feature
    print("\nLaunching scrcpy...")
    print("Physical screen will turn off automatically to prevent phantom touches.")
    print("You'll control via PC screen only.\n")

    # Start scrcpy with built-in screen management
    scrcpy_proc = subprocess.Popen([
        SCRCPY_PATH,
        "--turn-screen-off",  # Turn off physical screen (scrcpy's built-in feature)
        "--stay-awake",
        "--power-off-on-close",  # Turn screen back on when closing
        "--no-audio"  # Disable audio capture (requires unlocked screen on Android 11)
    ])

    print("✓ scrcpy launched! Physical screen will turn off automatically.")
    print("Control your phone via the PC window.\n")

    # Wait for scrcpy to close
    try:
        scrcpy_proc.wait()
    except KeyboardInterrupt:
        print("\nScrcpy closed")

    return 0

if __name__ == "__main__":
    sys.exit(main())
