# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Phone Control System for Redmi 10 2022 - A Python-based ADB connection manager with intelligent network discovery and scrcpy integration. **Cross-platform support for Windows and Linux** to control an Android phone via USB or wireless connection.

**Target Device**: Redmi 10 2022 (Model: 22011119UY, MAC: dc:6a:e7:06:b9:b8)

**Supported Platforms**: Windows, Linux (Arch Linux tested), macOS (should work)

## Core Architecture

### Three-Module System

1. **phone_connector.py** (PhoneConnector class)
   - Core connection logic with multi-tier discovery
   - Network scanning with MAC vendor identification
   - Connection caching and ADB command execution
   - Comprehensive logging to `phone_connector.log`

2. **launch_phone.py**
   - CLI launcher that connects phone and launches scrcpy
   - Manages physical screen lock-off with monitoring thread
   - Simple command-line interface for quick launches

3. **phone_control_gui.py** (PhoneControlGUI class)
   - Tkinter GUI for visual connection management
   - Threaded operations to keep UI responsive
   - Button controls for connect/disconnect/restart

### Connection Flow (Multi-Tier)

The `PhoneConnector.connect()` method tries three strategies in order:

```
1. USB Check (~5 sec)
   └─> check_usb_connection() - checks for USB-connected devices

2. Cached Connection (~7 sec)
   └─> try_cached_connection() - tries last known IP:PORT from connection_cache.json
       └─> Falls back to trying COMMON_PORTS on cached IP

3. Network Scan (~30-60 sec)
   └─> scan_network()
       ├─> get_local_networks() - detects all local subnets via ipconfig
       ├─> ping_sweep() - broadcasts pings to populate ARP cache
       ├─> get_arp_table() - extracts IP → MAC mappings
       ├─> identify_vendor() - matches MAC OUI to manufacturers (Xiaomi/Google/Samsung)
       ├─> Priority scan: cached MAC > Xiaomi > Android > others
       └─> port_scan_ip()
           ├─> Try COMMON_PORTS first (10 frequently-used ports)
           └─> Deep scan: Fast parallel TCP scan on ports 30000-50000
               └─> ADB verification on discovered open ports
```

### Key Design Patterns

**Thread-Safe Port Discovery**: Uses `threading.Event` (`stop_scanning`) to coordinate parallel port scans and stop immediately when a connection succeeds.

**Intelligent Prioritization**: Scans devices in order:
1. Cached MAC address (if known)
2. Xiaomi devices (high probability of being target)
3. Other Android manufacturers (Google, Samsung)
4. All other live hosts

**Caching System**: Stores last successful connection in `connection_cache.json`:
```json
{
  "ip": "192.168.0.x",
  "port": 36019,
  "mac": "dc:6a:e7:06:b9:b8",
  "device_model": "22011119UY",
  "device_name": "Redmi 10 2022",
  "last_connected": "ISO timestamp"
}
```

**Screen Management**: Both launcher scripts turn off the **physical screen** after scrcpy connects, with a monitoring thread that forces it back off if it turns on (preventing phantom touches while controlling via PC).

## Development Commands

### Running the Application

```bash
# CLI launcher (recommended for quick use)
python launch_phone.py

# GUI launcher (recommended for visual control)
python phone_control_gui.py

# Connection only (testing/debugging)
python phone_connector.py
```

### Testing Connection Strategies

```python
# Test individual connection methods:
from phone_connector import PhoneConnector

connector = PhoneConnector()
connector.check_usb_connection()        # Test USB
connector.try_cached_connection()       # Test cache
connector.scan_network()                # Test network scan
```

### Debugging

- **Logs**: Check `phone_connector.log` for detailed connection flow
- **Cache**: Inspect `connection_cache.json` for last known connection
- **ADB Commands**: All ADB operations go through `run_adb()` method

## Platform Considerations

### Cross-Platform Support

The codebase automatically detects the platform and uses appropriate commands:

**Windows**:
- **ADB Path**: Uses `scrcpy-win64-v3.3.3/adb.exe` (bundled with scrcpy)
- **Network**: Uses `ipconfig` command to detect subnets
- **ARP**: Uses `arp -a` with Windows format parsing
- **Ping**: Uses `-n` (count) and `-w` (timeout in milliseconds)
- **Process Kill**: Uses `taskkill /F /IM scrcpy.exe`

**Linux/macOS**:
- **ADB Path**: Uses system-installed `adb` (install via package manager)
- **Network**: Uses `ip -4 addr show` or falls back to `hostname -I`
- **ARP**: Uses `arp -a` with Linux format parsing
- **Ping**: Uses `-c` (count) and `-W` (timeout in seconds)
- **Process Kill**: Uses `pkill -9 scrcpy`

**Installation on Linux (Arch)**:
```bash
sudo pacman -S android-tools scrcpy
```

**Installation on Linux (Debian/Ubuntu)**:
```bash
sudo apt install adb scrcpy
```

### MIUI/Xiaomi-Specific Behavior

- Wireless debugging port changes frequently (after sleep/WiFi reconnect/reboot)
- Wireless debugging auto-disables after phone sleep
- Common ports: 43449, 35059, 36361, 40441, 37777, etc.
- Port range: Typically 30000-50000

## Important Paths & Files

**Windows**:
- **ADB Binary**: `scrcpy-win64-v3.3.3/adb.exe`
- **scrcpy Binary**: `scrcpy-win64-v3.3.3/scrcpy.exe`

**Linux/macOS**:
- **ADB Binary**: System `adb` (e.g., `/usr/bin/adb`)
- **scrcpy Binary**: System `scrcpy` (e.g., `/usr/bin/scrcpy`)

**All Platforms**:
- **Cache**: `connection_cache.json` (gitignored)
- **Logs**: `phone_connector.log` (gitignored)

## Modifying Connection Logic

### Adding New Connection Methods

Add to `PhoneConnector.connect()` in phone_connector.py:479-503. Follow the pattern:
1. Log the attempt
2. Try connection
3. Get device info if successful
4. Return True/False

### Changing Port Scan Strategy

- **Common ports**: Edit `COMMON_PORTS` list (phone_connector.py:26)
- **Port range**: Modify range in `port_scan_ip()` (phone_connector.py:321)
- **Parallel workers**: Adjust ThreadPoolExecutor `max_workers` (phone_connector.py:334)

### Customizing scrcpy Options

Edit the subprocess call in:
- CLI: `launch_phone.py:56-60`
- GUI: `phone_control_gui.py:142-146`

Common options:
- `--turn-screen-off`: Turn off screen during control (not used here; manual control instead)
- `--stay-awake`: Prevent phone from sleeping
- `--power-off-on-close`: Turn screen back on when closing
- `--max-fps 60`: Limit frame rate
- `--bit-rate 8M`: Set video bitrate

## Common Issues

### Port Changes Frequently
Normal MIUI behavior. The network scan will rediscover the new port automatically.

### Connection Fails After Sleep
Wireless debugging auto-disables on MIUI. Reconnect manually or use USB.

### Phantom Touches
The screen monitoring thread (launch_phone.py:16-39 and phone_control_gui.py:95-120) should prevent this by forcing the physical screen off. Check logs if screen turns on unexpectedly.

### Wrong Device Connected
If multiple Android devices are on the network, the code verifies device model (phone_connector.py:441-445) and disconnects if it doesn't match cached model.

## Code Style Notes

- **Logging**: Use `logger.info()` for user-visible progress, `logger.debug()` for detailed traces
- **Error Handling**: ADB commands use try/except with timeouts (run_adb method)
- **Thread Safety**: Use daemon threads for background monitoring so they don't prevent exit
- **Windows Compatibility**: All paths use `Path()` from pathlib for cross-platform compatibility

## Future Enhancement Areas

- ✅ ~~Add Linux/macOS support~~ (COMPLETED: Now cross-platform)
- Add USB-to-wireless bridge (connect via USB, enable wireless, switch to wireless)
- Implement auto-reconnect on connection loss
- Add support for multiple devices (device selection UI)
- Add scrcpy option presets (high quality, low latency, etc.)
- Package as standalone executables for each platform (PyInstaller)
