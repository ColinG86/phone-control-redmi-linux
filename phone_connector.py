#!/usr/bin/env python3
"""
Phone Connector - Comprehensive ADB connection manager with network scanning
"""

import subprocess
import socket
import struct
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple, Dict
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configuration
# Use system adb on Linux, bundled adb.exe on Windows
if sys.platform == 'win32':
    ADB_PATH = Path(__file__).parent / "scrcpy-win64-v3.3.3" / "adb.exe"
else:
    ADB_PATH = "adb"  # Use system adb on Linux/macOS
CACHE_FILE = Path(__file__).parent / "connection_cache.json"
LOG_FILE = Path(__file__).parent / "phone_connector.log"

# Common wireless debugging ports
COMMON_PORTS = [43449, 35059, 36361, 40441, 37777, 42222, 38888, 44973, 45678, 41234]

# Setup logging with UTF-8 encoding
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.INFO)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)

# Configure encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[file_handler, stream_handler]
)
logger = logging.getLogger(__name__)


class PhoneConnector:
    def __init__(self):
        self.cache = self.load_cache()
        self.adb_path = str(ADB_PATH)
        self.found_port = None  # For thread-safe port discovery
        self.stop_scanning = threading.Event()
        logger.info("=" * 70)
        logger.info("Phone Connector Starting")
        logger.info("=" * 70)

    def load_cache(self) -> dict:
        """Load cached connection info"""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                    logger.info(f"Loaded cache: {cache}")
                    return cache
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return {}

    def save_cache(self, ip: str, port: int, mac: str = None, device_name: str = None, device_model: str = None):
        """Save connection info to cache"""
        self.cache = {
            'ip': ip,
            'port': port,
            'mac': mac,
            'device_name': device_name,
            'device_model': device_model,
            'last_connected': datetime.now().isoformat()
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(self.cache, f, indent=2)
        logger.info(f"Saved cache: {self.cache}")

    def run_adb(self, *args, timeout=10) -> Tuple[int, str, str]:
        """Run ADB command and return (returncode, stdout, stderr)"""
        cmd = [self.adb_path] + list(args)
        logger.debug(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return -1, "", "Timeout"
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return -1, "", str(e)

    def get_local_networks(self) -> List[str]:
        """Get all local network subnets (e.g., ['192.168.0', '10.0.0'])"""
        subnets = []
        try:
            # Get network configuration - platform specific
            if sys.platform == 'win32':
                result = subprocess.run(['ipconfig'], capture_output=True, text=True)
                # Extract IPv4 addresses
                for line in result.stdout.split('\n'):
                    if 'IPv4' in line:
                        match = re.search(r'(\d+\.\d+\.\d+)\.\d+', line)
                        if match:
                            subnet = match.group(1)
                            if not subnet.startswith('127.'):
                                subnets.append(subnet)
                                logger.info(f"Found subnet: {subnet}.x")
            else:
                # Linux/macOS - use ip or hostname command
                try:
                    result = subprocess.run(['ip', '-4', 'addr', 'show'], capture_output=True, text=True)
                    # Look for inet lines like: inet 192.168.0.100/24
                    for line in result.stdout.split('\n'):
                        if 'inet ' in line and 'scope global' in line:
                            match = re.search(r'inet\s+(\d+\.\d+\.\d+)\.\d+', line)
                            if match:
                                subnet = match.group(1)
                                if not subnet.startswith('127.'):
                                    subnets.append(subnet)
                                    logger.info(f"Found subnet: {subnet}.x")
                except FileNotFoundError:
                    # Fallback to hostname command if ip command not available
                    result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
                    for ip_addr in result.stdout.strip().split():
                        match = re.search(r'(\d+\.\d+\.\d+)\.\d+', ip_addr)
                        if match:
                            subnet = match.group(1)
                            if not subnet.startswith('127.'):
                                subnets.append(subnet)
                                logger.info(f"Found subnet: {subnet}.x")

        except Exception as e:
            logger.error(f"Failed to get network info: {e}")

        return subnets

    def check_usb_connection(self) -> bool:
        """Check if phone is connected via USB"""
        logger.info("[1/4] Checking USB connection...")

        # Restart ADB server
        self.run_adb('kill-server')
        time.sleep(1)
        self.run_adb('start-server')
        time.sleep(2)

        # Check for devices
        rc, stdout, stderr = self.run_adb('devices')

        for line in stdout.split('\n'):
            if '\tdevice' in line and ':' not in line:  # USB devices don't have : in ID
                logger.info("[OK] USB connection found!")
                return True

        logger.info("  USB not connected")
        return False

    def try_connect(self, ip: str, port: int) -> bool:
        """Try to connect to specific IP:PORT"""
        address = f"{ip}:{port}"
        logger.debug(f"Trying {address}...")

        rc, stdout, stderr = self.run_adb('connect', address, timeout=5)

        if 'connected' in stdout.lower() or 'already connected' in stdout.lower():
            # Verify connection
            time.sleep(1)
            rc, stdout, stderr = self.run_adb('devices')

            for line in stdout.split('\n'):
                if address in line and '\tdevice' in line:
                    logger.info(f"[OK] Connected to {address}")
                    return True

        return False

    def try_cached_connection(self) -> bool:
        """Try to connect using cached IP and port"""
        if not self.cache.get('ip') or not self.cache.get('port'):
            logger.info("[2/4] No cached connection info")
            return False

        logger.info("[2/4] Trying cached connection...")
        ip = self.cache['ip']
        port = self.cache['port']

        if self.try_connect(ip, port):
            return True

        # Try known IP with different ports
        logger.info(f"  Cached port failed, trying other ports on {ip}...")
        for port in COMMON_PORTS:
            if self.try_connect(ip, port):
                self.save_cache(ip, port, self.cache.get('mac'), self.cache.get('device_name'))
                return True

        logger.info("  Cached connection failed")
        return False

    def get_arp_table(self) -> Dict[str, Dict[str, str]]:
        """Get ARP table with IP -> {mac, type} mapping"""
        arp_table = {}
        try:
            if sys.platform == 'win32':
                # Windows: use arp -a
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    # Windows format: 192.168.0.3      00-11-22-33-44-55     dynamic
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+([\w-]+)\s+(\w+)', line)
                    if match:
                        ip, mac, arp_type = match.groups()
                        mac = mac.lower().replace('-', ':')
                        arp_table[ip] = {'mac': mac, 'type': arp_type.lower()}
            else:
                # Linux/macOS: use ip neigh (modern) or fallback to arp -a
                try:
                    result = subprocess.run(['ip', 'neigh', 'show'], capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        # ip neigh format: 192.168.0.5 dev wlan0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)\s+dev\s+\S+\s+lladdr\s+([\w:]+)\s+(\w+)', line)
                        if match:
                            ip, mac, arp_type = match.groups()
                            mac = mac.lower()
                            # Map ip neigh states to arp types (REACHABLE/STALE = dynamic, PERMANENT = static)
                            arp_type = 'dynamic' if arp_type.lower() in ['reachable', 'stale', 'delay', 'probe'] else arp_type.lower()
                            arp_table[ip] = {'mac': mac, 'type': arp_type}
                except FileNotFoundError:
                    # Fallback to arp -a if ip command not available
                    result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        # arp format: ? (192.168.0.3) at aa:bb:cc:dd:ee:ff [ether] on wlan0
                        match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([\w:]+)\s+\[(\w+)\]', line)
                        if match:
                            ip, mac, arp_type = match.groups()
                            mac = mac.lower()
                            arp_table[ip] = {'mac': mac, 'type': arp_type.lower()}
        except Exception as e:
            logger.error(f"Failed to get ARP table: {e}")

        return arp_table

    def ping_sweep(self, subnet: str) -> List[str]:
        """Fast ping sweep to populate ARP table and find live hosts"""
        logger.info(f"  Pinging {subnet}.x to discover live devices...")

        # Platform-specific ping syntax
        if sys.platform == 'win32':
            ping_count = ['-n', '1']
            ping_timeout = ['-w', '100']
            ping_timeout_ms = '200'
        else:
            ping_count = ['-c', '1']
            ping_timeout = ['-W', '1']  # Linux timeout is in seconds
            ping_timeout_ms = '1'

        # Ping broadcast address to populate ARP cache quickly
        broadcast = f"{subnet}.255"
        subprocess.run(['ping'] + ping_count + ping_timeout + [broadcast],
                      capture_output=True, timeout=2)

        # Also ping common addresses to wake them up
        common_hosts = [1, 2, 3, 4, 5, 10, 100, 101, 102, 103, 104, 105]
        for host in common_hosts:
            ip = f"{subnet}.{host}"
            subprocess.Popen(['ping'] + ping_count + ['-W', ping_timeout_ms, ip],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

        # Wait for pings to complete
        time.sleep(1)

        # Now get fresh ARP table
        arp_table = self.get_arp_table()
        live_hosts = [ip for ip, info in arp_table.items()
                     if info['type'] == 'dynamic' and ip.startswith(subnet)]

        logger.info(f"  Found {len(live_hosts)} live device(s) on {subnet}.x")
        for ip in live_hosts[:10]:  # Show first 10
            mac = arp_table[ip]['mac']
            vendor = self.identify_vendor(mac)
            logger.info(f"    {ip} - {mac} ({vendor})")

        return live_hosts

    def identify_vendor(self, mac: str) -> str:
        """Identify device vendor from MAC address OUI"""
        # Common Android/Xiaomi OUIs
        vendors = {
            '00:9e:c8': 'Xiaomi',
            '34:ce:00': 'Xiaomi',
            '64:09:80': 'Xiaomi',
            '74:51:ba': 'Xiaomi',
            '78:11:dc': 'Xiaomi',
            'f8:a4:5f': 'Xiaomi',
            '50:8f:4c': 'Xiaomi',
            'ac:c1:ee': 'Xiaomi',
            'f4:8e:92': 'Xiaomi',
            '28:6c:07': 'Xiaomi',
            '38:a4:ed': 'Xiaomi',
            '04:cf:4b': 'Xiaomi',
            '18:59:36': 'Xiaomi',
            '98:fa:e3': 'Xiaomi',
            'c4:0b:cb': 'Xiaomi',
            'dc:6a:e7': 'Xiaomi',  # Your Redmi 10 2022
            # Add more common Android manufacturers
            '00:1a:11': 'Google',
            'ac:37:43': 'Google',
            'f4:f5:e8': 'Google',
            '08:00:27': 'Samsung',
            '1c:62:b8': 'Samsung',
            '2c:44:01': 'Samsung',
        }

        oui = ':'.join(mac.split(':')[:3])
        return vendors.get(oui, 'Unknown')

    def tcp_port_check(self, ip: str, port: int, timeout: float = 0.2) -> bool:
        """Quick TCP port connectivity check"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            sock.close()
            return False

    def try_port_batch(self, ip: str, ports: List[int]) -> Optional[int]:
        """Try connecting to a batch of ports, return first success"""
        if self.stop_scanning.is_set():
            return None

        for port in ports:
            if self.stop_scanning.is_set():
                return None

            if self.try_connect(ip, port):
                self.found_port = port
                self.stop_scanning.set()
                return port
        return None

    def port_scan_ip(self, ip: str, is_android_likely: bool = False) -> Optional[int]:
        """Scan all common ports on a specific IP and try ADB connect"""
        self.found_port = None
        self.stop_scanning.clear()

        # First try direct ADB connect on all common ports
        for port in COMMON_PORTS:
            if self.try_connect(ip, port):
                return port

        # If common ports failed and this looks like an Android device, do deeper scan
        if not is_android_likely:
            logger.debug(f"    Skipping deep port scan for non-Android device")
            return None

        logger.info(f"    Deep scanning wireless debug range (30000-50000)...")
        logger.info(f"    Step 1: Fast TCP port scan...")

        # Step 1: Fast parallel TCP scan to find open ports
        open_ports = []
        port_range = list(range(30000, 50000))

        def check_ports_batch(ports_batch):
            found = []
            for p in ports_batch:
                if self.tcp_port_check(ip, p, timeout=0.1):
                    found.append(p)
            return found

        # Split into batches for parallel scanning
        batch_size = 200
        batches = [port_range[i:i+batch_size] for i in range(0, len(port_range), batch_size)]

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check_ports_batch, batch): batch for batch in batches}

            for idx, future in enumerate(as_completed(futures)):
                found = future.result()
                open_ports.extend(found)

                if idx % 20 == 0:
                    logger.info(f"      TCP scan progress: {(idx*batch_size)}/{len(port_range)} ports...")

                if open_ports:
                    break  # Found some open ports, stop TCP scan

        if not open_ports:
            logger.info(f"    No open ports found in wireless debug range")
            return None

        logger.info(f"    Step 2: Found {len(open_ports)} open port(s), trying ADB connect...")
        for port in open_ports:
            logger.info(f"      Trying port {port}...")
            if self.try_connect(ip, port):
                return port

        return None

    def scan_network(self) -> bool:
        """Comprehensive network scan to find phone"""
        logger.info("[3/4] Scanning network for phone...")

        subnets = self.get_local_networks()
        if not subnets:
            logger.error("No network subnets found!")
            return False

        cached_mac = self.cache.get('mac')
        cached_model = self.cache.get('device_model')

        logger.info(f"Looking for: {cached_model or 'Any Android device'}")
        if cached_mac:
            logger.info(f"Cached MAC: {cached_mac}")

        for subnet in subnets:
            logger.info(f"\nScanning {subnet}.x...")

            # Step 1: Ping sweep to discover live devices
            live_hosts = self.ping_sweep(subnet)

            if not live_hosts:
                logger.info(f"  No live hosts found on {subnet}.x")
                continue

            # Step 2: Get ARP table with vendor info
            arp_table = self.get_arp_table()

            # Step 3: Prioritize devices
            prioritized = []
            xiaomi_devices = []
            android_devices = []
            other_devices = []

            for ip in live_hosts:
                if ip not in arp_table:
                    continue

                mac = arp_table[ip]['mac']
                vendor = self.identify_vendor(mac)

                # Check if this is our cached device
                if cached_mac and mac == cached_mac:
                    logger.info(f"  *** Found cached MAC! Trying {ip} first ***")
                    prioritized.insert(0, ip)
                    continue

                # Prioritize by vendor
                if 'xiaomi' in vendor.lower():
                    xiaomi_devices.append(ip)
                elif 'google' in vendor.lower() or 'samsung' in vendor.lower():
                    android_devices.append(ip)
                else:
                    other_devices.append(ip)

            # Build scan order: cached device > Xiaomi > Android > others
            scan_order = prioritized + xiaomi_devices + android_devices + other_devices

            logger.info(f"  Scan order: {len(scan_order)} device(s)")
            if xiaomi_devices:
                logger.info(f"    - {len(xiaomi_devices)} Xiaomi device(s) (high priority)")
            if android_devices:
                logger.info(f"    - {len(android_devices)} Android device(s)")

            # Step 4: Port scan prioritized devices
            for idx, ip in enumerate(scan_order, 1):
                mac = arp_table.get(ip, {}).get('mac', 'unknown')
                vendor = self.identify_vendor(mac) if mac != 'unknown' else 'Unknown'

                # Determine if this is likely an Android device
                is_android = vendor.lower() in ['xiaomi', 'google', 'samsung', 'oneplus', 'oppo']
                is_android = is_android or (cached_mac and mac == cached_mac)

                logger.info(f"  [{idx}/{len(scan_order)}] Trying {ip} ({vendor})...")

                port = self.port_scan_ip(ip, is_android_likely=is_android)
                if port:
                    logger.info(f"  SUCCESS! Connected to {ip}:{port}")
                    device_info = self.get_device_info()

                    # Verify it's the right device if we know the model
                    if cached_model and device_info.get('model') != cached_model:
                        logger.warning(f"    Wrong device: {device_info.get('model')} (expected {cached_model})")
                        # Disconnect and continue
                        self.run_adb('disconnect', f"{ip}:{port}")
                        continue

                    logger.info(f"    Device: {device_info.get('manufacturer')} {device_info.get('model')}")
                    self.save_cache(ip, port, mac,
                                  device_info.get('device_name'),
                                  device_info.get('model'))
                    return True

        logger.info("\nNetwork scan complete - no phone found")
        return False

    def get_device_info(self) -> dict:
        """Get detailed info about connected device"""
        info = {}

        # Get device model
        rc, stdout, stderr = self.run_adb('shell', 'getprop', 'ro.product.model')
        info['model'] = stdout.strip()

        # Get device manufacturer
        rc, stdout, stderr = self.run_adb('shell', 'getprop', 'ro.product.manufacturer')
        info['manufacturer'] = stdout.strip()

        # Get Android version
        rc, stdout, stderr = self.run_adb('shell', 'getprop', 'ro.build.version.release')
        info['android_version'] = stdout.strip()

        # Get device name
        rc, stdout, stderr = self.run_adb('shell', 'settings', 'get', 'global', 'device_name')
        info['device_name'] = stdout.strip()

        logger.info(f"Device info: {info}")
        return info

    def connect(self) -> bool:
        """Main connection flow"""
        # Try USB first
        if self.check_usb_connection():
            device_info = self.get_device_info()
            return True

        # Try cached wireless connection
        if self.try_cached_connection():
            device_info = self.get_device_info()
            return True

        # Full network scan
        if self.scan_network():
            device_info = self.get_device_info()
            return True

        logger.error("=" * 70)
        logger.error("CONNECTION FAILED")
        logger.error("=" * 70)
        logger.error("Troubleshooting:")
        logger.error("1. USB: Plug in cable, enable USB debugging, allow computer")
        logger.error("2. Wireless: Enable Wireless Debugging in Developer Options")
        logger.error("3. Network: Ensure phone and PC on same WiFi network")
        return False


def main():
    connector = PhoneConnector()

    if connector.connect():
        logger.info("=" * 70)
        logger.info("[SUCCESS] PHONE CONNECTED")
        logger.info("=" * 70)
        logger.info(f"Cache: {connector.cache}")
        logger.info("\nReady to launch scrcpy!")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
