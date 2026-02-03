# Project Guidelines for AI Agents

## Project Overview

This is a Zephyr RTOS project for Raspberry Pi Pico 2 W, using Zenoh-Pico for communication and NanoPB for Protobuf with RPC service.

## Environment

- **OS**: Ubuntu 24.04 (Dev Container)
- **Build System**: West (Zephyr's meta-tool) + CMake + Ninja
- **Target Board**: Raspberry Pi Pico 2 W (`rpi_pico2/rp2350a/w`)
- **Language**: C++ (C++20)

## Python Environment

- **Package Manager**: Use `uv` (NOT pip directly)
- **Dependencies**: Managed via `pyproject.toml` at repo root

### Running Python scripts

```bash
# Use uv run to ensure correct environment
uv run  <script.py>
```

## Comment

Comments must be in English. 
Write a method comment in the following styles:

- C++: doxygen
- Python: Google docstring

## Building Flash and Monitor

Generate Protobuf only

```bash
uv run python build.py --proto-only
```

Build only

```bash
uv run python build.py --build-only
```

Build and Run

```bash
uv run python build.py
```

Options of build.py is following:

```txt
  -h, --help            show this help message and exit
  -a APP, --app APP     Application directory (default: apps/zenoh_rpc)
  -p, --pristine        Pristine build (clean rebuild)
  --proto-only          Only generate protobuf code, don't build, flash, or monitor
  --build-only          Only build, don't flash or monitor
  --flash-only          Only flash, don't build or monitor
  --monitor-only        Only monitor, don't build or flash
  --port PORT           Serial port for monitoring (auto-detect if not specified)
  --baudrate BAUDRATE   Serial baudrate (default: 921600)
  --runner {openocd,uf2,probe-rs,jlink}
                        Flash runner to use (default: openocd)
```

### Test with Python Script

Start Zenoh Router

```bash
uv run tools/start_router.py
```

Run example client to test RPC and subscribe

```bash
uv run tools/example_client.py
```

## Project Structure

```
.
├── README.md              
├── AGENTS.md              # This file
├── pyproject.toml         # Python dependencies
├── manifest/
│   └── west.yml           # Zephyr manifest
├── apps/
│   └── zenoh_rpc/         # Zenoh RPC application
├── bootloader/
│   └── mcuboot/           # MCUboot bootloader
├── modules/lib/
│   ├── zephyr/            # Zephyr RTOS
│   ├── zenoh-pico/        # Zenoh-Pico library
│   └── nanopb/            # NanoPB library
├── tools/
│   └── zenoh_rpc/         # Python client scripts for PC
└── build/                 # Build output directory
```

