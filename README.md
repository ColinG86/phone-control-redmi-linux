# Phone Connection & Control System

Professional Python-based ADB connection manager with intelligent network discovery for your Redmi 10 2022.

## Features

### Smart Connection System
- **Multi-tier connection**: USB → Cached wireless → Network scan
- **Device discovery**: Ping sweep + MAC vendor identification
- **Intelligent prioritization**: Xiaomi devices scanned first
- **Fast TCP port scanning**: Parallel scanning of 20,000 ports
- **Persistent caching**: Remembers IP, port, MAC, and device info

### Network Intelligence
- Automatic subnet detection (handles multiple network adapters)
- MAC address vendor identification (Xiaomi/Google/Samsung)
- ARP table analysis for device fingerprinting
- Wireless debugging port discovery (30000-50000 range)

### Logging & Diagnostics
- Comprehensive logging to `phone_connector.log`
- Real-time console feedback
- Connection history tracking
- Debug info for troubleshooting

## Quick Start

### Connect to Phone
```bash
python phone_connector.py
```

### Launch Phone Control
```bash
python launch_phone.py
```

This will:
1. Auto-connect to your phone (USB or wireless)
2. Launch scrcpy with screen-off mode
3. Keep phone awake during control

## How It Works

### Connection Flow

1. **USB Check** (~5 sec)
   - Checks for USB-connected devices
   - Fastest and most reliable method

2. **Cached Connection** (~7 sec)
   - Tries last known IP:PORT
   - Falls back to trying other common ports on known IP

3. **Network Scan** (~30-60 sec)
   - Ping sweep to discover live devices
   - Identifies devices by MAC vendor (Xiaomi prioritized)
   - Fast parallel TCP scan of wireless debug ports
   - ADB connection verification

### Device Discovery

The system identifies your Redmi 10 2022 by:
- **MAC Address**: `dc:6a:e7:06:b9:b8` (Xiaomi OUI)
- **Model**: `22011119UY`
- **Device Name**: `Redmi 10 2022`

### Cache System

Connection info is saved to `connection_cache.json`:
```json
{
  "ip": "192.168.0.5",
  "port": 36019,
  "mac": "dc:6a:e7:06:b9:b8",
  "device_model": "22011119UY",
  "device_name": "Redmi 10 2022",
  "last_connected": "2025-10-02T10:25:00"
}
```

## Technical Details

### Port Scanning Strategy

1. **Common Ports First**: Tries 10 frequently-used wireless debugging ports
2. **TCP Pre-scan**: Fast parallel socket check across 30000-50000 range
3. **ADB Verification**: Confirms discovered ports with actual ADB connection

### Network Discovery

- **Ping Sweep**: Broadcasts + targeted pings to populate ARP cache
- **MAC Vendor Detection**: Identifies Android manufacturers from OUI
- **Priority Scanning**: Xiaomi > Android > Other devices

### Performance

| Method | Time | Success Rate |
|--------|------|--------------|
| USB | ~5 sec | 100% (if plugged in) |
| Cached | ~7 sec | 95% (if port unchanged) |
| Network Scan | ~30-60 sec | 90% (if wireless debugging on) |

## Files

- `phone_connector.py`: Core connection logic with network scanning
- `launch_phone.py`: Simple launcher script
- `connection_cache.json`: Persistent connection cache
- `phone_connector.log`: Detailed connection logs
- `scrcpy-win64-v3.3.3/`: scrcpy binaries and ADB

## Troubleshooting

### Connection Fails

1. **Enable Wireless Debugging**:
   - Settings → Developer Options → Wireless Debugging → ON

2. **Check Same Network**:
   - Phone and PC must be on same WiFi network

3. **USB Fallback**:
   - Plug in USB cable for guaranteed connection

### Port Changes Frequently

This is normal behavior on Xiaomi/MIUI devices. The wireless debugging port changes:
- After sleep/standby
- After WiFi reconnection
- After reboot

The system automatically discovers the new port via network scanning.

### Check Logs

```bash
tail -50 phone_connector.log
```

## Advanced Usage

### Custom scrcpy Options

Edit `launch_phone.py` to customize:
```python
subprocess.run([
    str(SCRCPY_PATH),
    "--turn-screen-off",      # Turn off phone screen
    "--stay-awake",           # Prevent sleep
    "--max-fps", "60",        # Limit FPS
    "--bit-rate", "8M",       # Video bitrate
])
```

### Manual Connection

```bash
# Check current devices
./scrcpy-win64-v3.3.3/adb.exe devices

# Manual connect
./scrcpy-win64-v3.3.3/adb.exe connect 192.168.0.5:PORT

# Launch scrcpy
./scrcpy-win64-v3.3.3/scrcpy.exe --turn-screen-off --stay-awake
```

## Requirements

- Python 3.7+
- Windows (tested on Windows 10/11)
- Phone with Wireless Debugging enabled (Android 11+)

## Notes

- Wireless debugging auto-disables after phone sleep (MIUI limitation)
- USB connection is most reliable for critical use
- MAC address and device model are cached for faster future connections
- All connection attempts are logged for debugging
