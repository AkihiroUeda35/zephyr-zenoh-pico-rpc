#!/usr/bin/env python3
import os
import sys
import logging
import signal
import zenoh
import argparse
from nicegui import ui, app


from rpc.zenoh_rpc_client import ZenohRpcClient
from rpc import service_gui

logging.basicConfig(level=logging.INFO)

DEVICE_ID = "pico2w-001"
DEFAULT_ROUTER = "tcp/127.0.0.1:7447"


def main():
    # parse CLI args to override defaults
    parser = argparse.ArgumentParser(description="Zenoh RPC GUI")
    parser.add_argument("--device-id", default=DEVICE_ID, help="Device ID (default: pico2w-001)")
    parser.add_argument("--router", default=DEFAULT_ROUTER, help="Zenoh router endpoint (default: tcp/127.0.0.1:7447)")
    args = parser.parse_args()

    # Zenoh setup
    conf = zenoh.Config()
    conf.insert_json5("mode", '"client"')
    conf.insert_json5("connect/endpoints", f'["{args.router}"]')

    logging.info(f"Opening Zenoh session to {args.router}...")
    session = zenoh.open(conf)
    zenoh_client = ZenohRpcClient(session, args.device_id)

    @ui.page("/")
    def index():
        service_gui.create_ui(zenoh_client, args.device_id)

    script_dir = os.path.dirname(__file__)
    ui.run(
        title="Zenoh RPC GUI",
        reload=True,
        uvicorn_reload_dirs=f"{script_dir},{script_dir}/rpc",
        storage_secret="zenoh-rpc-gui-secret",
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
