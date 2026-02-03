#!/usr/bin/env python3
"""
Build, flash, and monitor script for Zephyr RTOS on Raspberry Pi Pico 2 W
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
import serial.tools.list_ports


BOARD = "rpi_pico2/rp2350a/m33/w"
WORKSPACE_ROOT = Path(__file__).parent
DEFAULT_APP = "apps/zenoh_rpc"
if os.name != "nt":
    NANOPB_GENERATOR = WORKSPACE_ROOT / "modules/lib/nanopb/generator/protoc-gen-nanopb"
else:
    NANOPB_GENERATOR = WORKSPACE_ROOT / "modules/lib/nanopb/generator/protoc-gen-nanopb.bat"

NANOPB_PROTO_PATH = WORKSPACE_ROOT / "modules/lib/nanopb/generator/proto"

# OpenOCD installed in Zephyr SDK
ZEPHYR_SDK_DIR = os.environ.get("ZEPHYR_SDK_INSTALL_DIR", "/opt/zephyr-sdk-0.17.0")
OPENOCD_BIN = Path(ZEPHYR_SDK_DIR) / "sysroots/x86_64-pokysdk-linux/usr/bin/openocd"


def find_pico_uart_port():
    """Find the Raspberry Pi Pico serial port (USB CDC ACM)."""
    PICO_DEBUGGER_PID_VID = "2e8a:000c"
    ports = serial.tools.list_ports.comports()

    # Look for Pico (common patterns)
    for port in ports:
        # Check for CDC ACM or Pico device
        print(f"Checking port: {port.device}, hwid: {port.hwid}")
        if any(x in port.hwid.lower() for x in [PICO_DEBUGGER_PID_VID.lower()]):
            print(f"Found Pico device on port: {port.device}, hwid: {port.hwid}")
            return port.device

    # If no specific match, return first available port
    if ports:
        print(f"No specific Pico device found, using first available port: {ports[0].device}")
        return ports[0].device

    return None


def run_command(cmd, cwd=None, check=True):
    """Run a shell command and print output in real-time."""
    print(f"\n{'=' * 60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"{'=' * 60}\n")

    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd or WORKSPACE_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in process.stdout:
            print(line, end="")

        process.wait()

        if check and process.returncode != 0:
            print(f"\n❌ Command failed with exit code {process.returncode}")
            return False

        print(f"\n✅ Command completed successfully")
        return True

    except Exception as e:
        print(f"\n❌ Error running command: {e}")
        return False


def build(app_path, pristine=False):
    """Build the Zephyr application."""
    cmd = ["west", "build", "-b", BOARD]

    if pristine:
        cmd.extend(["-p", "always"])

    cmd.append(str(app_path))

    return run_command(cmd)


def generate_proto(app_path):
    """Generate NanoPB (C) and Python code from .proto files."""
    proto_file = app_path / "service.proto"

    if not proto_file.exists():
        print(f"ℹ️  No service.proto found in {app_path}, skipping code generation")
        return True

    print(f"\n{'=' * 60}")
    print(f"Generating code from {proto_file}")
    print(f"{'=' * 60}\n")

    # Create output directories
    tools_dir = WORKSPACE_ROOT / "tools"
    os.makedirs(f"{app_path}/rpc", exist_ok=True)
    os.makedirs(f"{tools_dir}/rpc", exist_ok=True)

    # Generate all code with single protoc command
    print("📦 Generating NanoPB C code, Python code, RPC stubs, and NiceGUI app...")

    protoc_cmd = [
        "protoc",
        f"--plugin=protoc-gen-nanopb={NANOPB_GENERATOR}",
        f"--plugin=protoc-gen-custom_client={WORKSPACE_ROOT}/generator/gen_client_python.py",
        f"--plugin=protoc-gen-custom_server={WORKSPACE_ROOT}/generator/gen_server_nanopb.py",
        f"--plugin=protoc-gen-nicegui={WORKSPACE_ROOT}/generator/gen_nicegui.py",
        f"--proto_path={app_path}",
        f"--proto_path={NANOPB_PROTO_PATH}",
        f"--nanopb_opt=-I{app_path}",
        f"--custom_server_opt=-I{app_path}",
        f"--nanopb_out={app_path}/rpc",
        f"--python_out={tools_dir}/rpc",
        f"--pyi_out={tools_dir}/rpc",
        f"--custom_client_out={tools_dir}/rpc",
        f"--custom_server_out={app_path}/rpc",
        f"--nicegui_out={tools_dir}/rpc",
        str(proto_file),
    ]

    if not run_command(protoc_cmd, cwd=WORKSPACE_ROOT):
        return False

    print("\n✅ Code generation completed successfully")
    return True


def flash(runner="openocd"):
    """Flash the built application to the device."""
    cmd = ["west", "flash", "--runner", runner]
    return run_command(cmd)


def erase_nvs():
    """Erase NVS partition using OpenOCD.

    NVS partition is located at 0x3F0000 (4MB - 64KB) with size 0x10000 (64KB).
    This will erase Wi-Fi credentials and other stored settings.
    """
    if not OPENOCD_BIN.exists():
        print(f"❌ OpenOCD not found at: {OPENOCD_BIN}")
        print(f"   Please check ZEPHYR_SDK_INSTALL_DIR: {ZEPHYR_SDK_DIR}")
        return False

    print(f"\n{'=' * 60}")
    print("⚠️  WARNING: Erasing NVS partition (Wi-Fi credentials will be lost)")
    print(f"{'=' * 60}\n")

    # OpenOCD scripts directory
    openocd_scripts = Path(ZEPHYR_SDK_DIR) / "sysroots/x86_64-pokysdk-linux/usr/share/openocd/scripts"

    # OpenOCD command to erase NVS partition
    openocd_cmd = [
        "sudo",
        str(OPENOCD_BIN),
        "-s",
        str(openocd_scripts),
        "-f",
        "interface/cmsis-dap.cfg",
        "-f",
        "target/rp2350.cfg",
        "-c",
        "init; reset halt; flash erase_address 0x103F0000 0x10000; exit",
    ]

    return run_command(openocd_cmd)


def monitor(port=None, baudrate=921600):
    """Monitor serial output from the device."""
    if not port:
        port = find_pico_uart_port()

    if not port:
        print("❌ No serial port found. Please specify with --port")
        return False

    print(f"\n{'=' * 60}")
    print(f"Monitoring serial port: {port} @ {baudrate} baud")
    print(f"{'=' * 60}\n")

    try:
        # Give device time to reset after flashing
        time.sleep(2)

        import serial

        with serial.Serial(port, baudrate, timeout=1) as ser:
            while True:
                if ser.in_waiting:
                    data = ser.read(ser.in_waiting)
                    print(data.decode("utf-8", errors="replace"), end="")
                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped")
        return True
    except Exception as e:
        print(f"\n❌ Error during monitoring: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Build, flash, and monitor Zephyr application")

    parser.add_argument("-a", "--app", default=DEFAULT_APP, help=f"Application directory (default: {DEFAULT_APP})")

    parser.add_argument("-p", "--pristine", action="store_true", help="Pristine build (clean rebuild)")

    parser.add_argument(
        "--proto-only", action="store_true", help="Only generate protobuf code, don't build, flash, or monitor"
    )
    parser.add_argument("--build-only", action="store_true", help="Only build, don't flash or monitor")

    parser.add_argument("--flash-only", action="store_true", help="Only flash and monitor, don't build")

    parser.add_argument("--port", help="Serial port for monitoring (auto-detect if not specified)")

    parser.add_argument("--baudrate", type=int, default=921600, help="Serial baudrate (default: 921600)")

    parser.add_argument(
        "--runner",
        default="openocd",
        choices=["openocd", "uf2", "probe-rs", "jlink"],
        help="Flash runner to use (default: openocd)",
    )

    parser.add_argument(
        "--erase-nvs", action="store_true", help="Erase NVS partition (Wi-Fi credentials) using OpenOCD before flashing"
    )

    args = parser.parse_args()

    app_path = WORKSPACE_ROOT / args.app
    if not app_path.exists():
        print(f"❌ Application directory not found: {app_path}")
        return 1

    # Build
    if not args.flash_only:
        if not generate_proto(app_path):
            return 1
        if args.proto_only:
            return 0
        if not build(app_path, pristine=args.pristine):
            return 1

    # Erase NVS if requested
    if args.erase_nvs:
        if not erase_nvs():
            return 1

    # Flash
    if not args.build_only:
        if not flash(runner=args.runner):
            return 1
        if not monitor(port=args.port, baudrate=args.baudrate):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
