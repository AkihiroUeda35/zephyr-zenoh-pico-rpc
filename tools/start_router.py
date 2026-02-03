"""
Zenoh Router startup script.

Starts zenohd router that listens on TCP port 7447.
Devices (USB-ECM or Wi-Fi) connect to this router.

Usage:
    python start_router.py
"""

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import serial.tools.list_ports
except ImportError:
    serial = None

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def find_zenohd():
    """Find zenohd executable in PATH."""
    zenohd = shutil.which("zenohd")
    if not zenohd:
        # Also check for Windows zenohd.exe
        zenohd = shutil.which("zenohd.exe")
    return zenohd


def check_usb_device(vid_pid="2fe3:0100"):
    """Check if USB device with given VID:PID is connected and return serial port if found."""
    if serial is None:
        logger.warning("pyserial not available, cannot check for USB devices")
        return None

    try:
        vid, pid = vid_pid.split(":")
        target_vid = int(vid, 16)
        target_pid = int(pid, 16)

        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.vid == target_vid and port.pid == target_pid:
                return port.device
    except Exception as e:
        logger.warning(f"Error checking USB devices: {e}")
    return None


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Zenoh Router - Listens on TCP port 7447 for Pico devices",
    )
    parser.add_argument(
        "--connect-device",
        type=str,
        default="tcp/192.168.10.2:7447",
        help="Device endpoint to connect to (default: tcp/192.168.10.2:7447)",
    )
    return parser.parse_args()


def check_dependencies():
    """Check if required dependencies are available."""
    zenohd = find_zenohd()
    if not zenohd:
        logger.error("zenohd not found. Please install it first:")
        logger.info("  - Ubuntu/Debian: sudo apt install zenoh")
        logger.info("  - Windows: Download from https://download.eclipse.org/zenoh/zenoh/latest/")
        logger.info("  - macOS: brew install zenoh")
        logger.info("  - Or from source: cargo install zenoh")
        sys.exit(1)

    return zenohd


def build_zenohd_args(connect_device=None, serial_port=None):
    """Build zenohd command-line arguments."""
    # Listen on TCP for all devices (Python client, USB-ECM, Wi-Fi)
    args = ["-l", "tcp/0.0.0.0:7447"]

    # Add serial listener if device is connected
    if serial_port:
        args.extend(["-l", f"serial/{serial_port}#baudrate=115200"])

    # Connect to device endpoint if specified
    if connect_device:
        args.extend(["-e", connect_device])

    return args


def main():
    """Main entry point."""
    args = parse_args()
    zenohd_path = check_dependencies()

    # Check for USB device
    serial_port = check_usb_device()

    logger.info("=" * 60)
    logger.info("Starting Zenoh Router (zenohd)")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Listening on: tcp/0.0.0.0:7447")
    logger.info("  - Python client: tcp/localhost:7447")
    if serial_port:
        logger.info(f"  - Serial device: {serial_port} (baudrate=115200)")
    if args.connect_device:
        logger.info(f"  - Connecting to device: {args.connect_device}")
    else:
        logger.info("  - Pico devices: tcp/<router_ip>:7447 or multicast scouting")
    logger.info("")
    logger.info("Multicast scouting enabled for device auto-discovery")
    logger.info("=" * 60)
    logger.info("")

    zenohd_args = build_zenohd_args(args.connect_device, serial_port)
    logger.info(f"Running: {zenohd_path} {' '.join(zenohd_args)}")
    logger.info("")

    try:
        subprocess.run([zenohd_path] + zenohd_args, check=False)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to run zenohd: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
