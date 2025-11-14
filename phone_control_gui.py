#!/usr/bin/env python3
"""
Phone Control GUI - Simple interface for phone connection and control
"""

import sys
import subprocess
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from phone_connector import PhoneConnector

# Platform-specific paths
if sys.platform == 'win32':
    SCRCPY_PATH = Path(__file__).parent / "scrcpy-win64-v3.3.3" / "scrcpy.exe"
    ADB_PATH = Path(__file__).parent / "scrcpy-win64-v3.3.3" / "adb.exe"
else:
    SCRCPY_PATH = "scrcpy"  # Use system scrcpy on Linux/macOS
    ADB_PATH = "adb"  # Use system adb on Linux/macOS

class PhoneControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Phone Control - Redmi 10 2022")
        self.root.geometry("600x500")

        self.connector = None
        self.scrcpy_process = None
        self.monitor_thread = None
        self.keep_monitoring = False

        self.setup_ui()

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill=tk.X)

        title = tk.Label(header, text="📱 Phone Control", font=("Arial", 18, "bold"),
                        bg="#2c3e50", fg="white")
        title.pack(pady=15)

        # Connection Status
        status_frame = tk.Frame(self.root, bg="#ecf0f1", height=50)
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        self.status_label = tk.Label(status_frame, text="● Disconnected",
                                     font=("Arial", 12), bg="#ecf0f1", fg="#e74c3c")
        self.status_label.pack(pady=10)

        # Control Buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)

        self.connect_btn = tk.Button(button_frame, text="🔌 Connect & Launch",
                                     command=self.connect_and_launch,
                                     bg="#27ae60", fg="white", font=("Arial", 12, "bold"),
                                     width=20, height=2)
        self.connect_btn.grid(row=0, column=0, padx=10, pady=5)

        self.screen_btn = tk.Button(button_frame, text="🔒 Lock Screen OFF",
                                    command=self.toggle_screen,
                                    bg="#3498db", fg="white", font=("Arial", 12, "bold"),
                                    width=20, height=2, state=tk.DISABLED)
        self.screen_btn.grid(row=0, column=1, padx=10, pady=5)

        self.disconnect_btn = tk.Button(button_frame, text="❌ Disconnect",
                                        command=self.disconnect,
                                        bg="#e74c3c", fg="white", font=("Arial", 12, "bold"),
                                        width=20, height=2, state=tk.DISABLED)
        self.disconnect_btn.grid(row=1, column=0, padx=10, pady=5)

        self.restart_btn = tk.Button(button_frame, text="🔄 Restart Phone",
                                     command=self.restart_phone,
                                     bg="#95a5a6", fg="white", font=("Arial", 12, "bold"),
                                     width=20, height=2, state=tk.DISABLED)
        self.restart_btn.grid(row=1, column=1, padx=10, pady=5)

        # Info Panel
        info_frame = tk.LabelFrame(self.root, text="Connection Info", font=("Arial", 10, "bold"))
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.info_text = scrolledtext.ScrolledText(info_frame, height=10, wrap=tk.WORD,
                                                   font=("Consolas", 9))
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log("Phone Control GUI Ready")
        self.log("Click 'Connect & Launch' to start")

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.info_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.info_text.see(tk.END)

    def update_status(self, status, color):
        self.status_label.config(text=f"● {status}", fg=color)

    def keep_screen_off(self):
        """Monitor and keep phone screen off"""
        while self.keep_monitoring:
            time.sleep(2)
            if not self.keep_monitoring:
                break

            result = subprocess.run(
                f"{ADB_PATH} shell dumpsys power | grep mWakefulness",
                capture_output=True,
                text=True,
                shell=True
            )

            if "Awake" in result.stdout:
                self.log("Screen turned on, forcing off...")
                subprocess.run(
                    [ADB_PATH, "shell", "input", "keyevent", "KEYCODE_POWER"],
                    capture_output=True
                )
                time.sleep(0.5)
                subprocess.run(
                    [ADB_PATH, "shell", "input", "keyevent", "KEYCODE_POWER"],
                    capture_output=True
                )

    def connect_and_launch(self):
        self.connect_btn.config(state=tk.DISABLED)
        self.update_status("Connecting...", "#f39c12")
        self.log("Starting connection process...")

        def connect_thread():
            self.connector = PhoneConnector()

            if not self.connector.connect():
                self.root.after(0, lambda: self.log("❌ Connection failed!"))
                self.root.after(0, lambda: self.update_status("Connection Failed", "#e74c3c"))
                self.root.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                return

            cache = self.connector.cache
            self.root.after(0, lambda: self.log(f"✓ Connected to {cache.get('ip')}:{cache.get('port')}"))
            self.root.after(0, lambda: self.log(f"  Device: {cache.get('device_name')}"))
            self.root.after(0, lambda: self.update_status("Connected", "#27ae60"))

            # Launch scrcpy first (WITHOUT --turn-screen-off)
            self.root.after(0, lambda: self.log("Launching scrcpy window..."))
            self.scrcpy_process = subprocess.Popen([
                SCRCPY_PATH,
                "--stay-awake",
                "--power-off-on-close"
            ])

            # Wait for scrcpy to connect
            time.sleep(3)

            # Now turn PHYSICAL screen off
            self.root.after(0, lambda: self.log("Turning physical screen OFF (PC screen stays on)"))
            subprocess.run([ADB_PATH, "shell", "input", "keyevent", "KEYCODE_POWER"],
                         capture_output=True)
            time.sleep(0.5)

            # Start screen monitor
            self.keep_monitoring = True
            self.monitor_thread = threading.Thread(target=self.keep_screen_off, daemon=True)
            self.monitor_thread.start()
            self.root.after(0, lambda: self.log("Physical screen locked OFF - control via PC"))

            self.root.after(0, lambda: self.log("✓ scrcpy launched successfully"))
            self.root.after(0, lambda: self.screen_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.disconnect_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.restart_btn.config(state=tk.NORMAL))

        threading.Thread(target=connect_thread, daemon=True).start()

    def toggle_screen(self):
        if self.keep_monitoring:
            self.keep_monitoring = False
            self.log("Screen lock disabled")
            self.screen_btn.config(text="🔓 Allow Screen ON")
        else:
            self.keep_monitoring = True
            self.monitor_thread = threading.Thread(target=self.keep_screen_off, daemon=True)
            self.monitor_thread.start()
            self.log("Screen lock enabled")
            self.screen_btn.config(text="🔒 Lock Screen OFF")

    def restart_phone(self):
        if tk.messagebox.askyesno("Restart Phone", "Are you sure you want to restart the phone?"):
            self.log("Restarting phone...")
            subprocess.run([ADB_PATH, "reboot"], capture_output=True)
            self.disconnect()

    def disconnect(self):
        self.log("Disconnecting...")
        self.keep_monitoring = False

        if self.scrcpy_process:
            self.scrcpy_process.terminate()
            self.scrcpy_process = None

        # Kill any remaining scrcpy processes
        if sys.platform == 'win32':
            subprocess.run(["taskkill", "/F", "/IM", "scrcpy.exe"],
                          capture_output=True, shell=True)
        else:
            subprocess.run(["pkill", "-9", "scrcpy"],
                          capture_output=True)

        self.log("✓ Disconnected")
        self.update_status("Disconnected", "#e74c3c")
        self.connect_btn.config(state=tk.NORMAL)
        self.screen_btn.config(state=tk.DISABLED)
        self.disconnect_btn.config(state=tk.DISABLED)
        self.restart_btn.config(state=tk.DISABLED)

    def on_closing(self):
        self.disconnect()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = PhoneControlGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
