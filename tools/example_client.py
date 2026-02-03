"""
Example client for Zenoh RPC DeviceService.

Usage:
    # Connect to local router (default)
    uv run python tools/example_client.py

    # Connect to specific router
    uv run python tools/example_client.py --connect tcp/192.168.1.100:7447

    # Use multicast scouting (auto-discover router)
    uv run python tools/example_client.py --scouting
"""

import argparse
import logging
import time

import zenoh
import rpc.service_pb2 as pb
from rpc.zenoh_rpc_client import ZenohRpcClient, ZenohSubscriberClient, LogSubscriber
from rpc.service_client import DeviceServiceClient, TelemetrySubscriber

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEVICE_ID = "pico2w-001"
DEFAULT_ROUTER = "tcp/127.0.0.1:7447"


def parse_args():
    parser = argparse.ArgumentParser(description="Zenoh RPC Example Client")
    parser.add_argument(
        "-c",
        "--connect",
        type=str,
        default=DEFAULT_ROUTER,
        help=f"Router endpoint to connect to (default: {DEFAULT_ROUTER})",
    )
    parser.add_argument(
        "-s", "--scouting", action="store_true", help="Use multicast scouting to discover router (ignores --connect)"
    )
    parser.add_argument(
        "-d", "--device-id", type=str, default=DEVICE_ID, help=f"Device ID for telemetry topics (default: {DEVICE_ID})"
    )
    return parser.parse_args()


def on_sensor_data(data: pb.SensorTelemetry):
    """Callback for sensor telemetry."""
    logger.info(f"Sensor: temp={data.temperature:.2f}°C, humidity={data.humidity:.2f}%")


def on_log_message(message: str):
    """Callback for log messages."""
    logger.info(f"Device Log: {message}")


def main():
    args = parse_args()

    logger.info("Starting Zenoh RPC Example Client")

    # Configure Zenoh
    config = zenoh.Config()

    if args.scouting:
        # Use multicast scouting to auto-discover router
        logger.info("Using multicast scouting to discover router...")
        # Default config enables scouting
    else:
        # Connect to specific router endpoint
        logger.info(f"Connecting to router: {args.connect}")
        config.insert_json5("connect/endpoints", f'["{args.connect}"]')
        # Disable scouting when using explicit endpoint
        config.insert_json5("scouting/multicast/enabled", "false")

    logger.info("Opening Zenoh session...")
    session = zenoh.open(config)

    try:
        # Create RPC and Subscriber clients
        rpc_client = ZenohRpcClient(session, args.device_id)
        sub_client = ZenohSubscriberClient(session)

        # Create service client and telemetry subscriber
        device_service = DeviceServiceClient(rpc_client)
        telemetry = TelemetrySubscriber(sub_client, args.device_id)
        log = LogSubscriber(sub_client, args.device_id)
        # Subscribe to telemetry and logs
        telemetry.subscribe_sensor(on_sensor_data)
        log.subscribe(on_log_message)
        logger.info("Subscribed to telemetry and logs")

        # Example RPC calls
        logger.info("--- RPC Examples ---")

        # Echo
        logger.info("Calling Echo...")
        response, echo_msg = device_service.echo(msg="Hello, Pico!")
        if response.success:
            logger.info(f"Echo response: {echo_msg}")
        else:
            logger.error(f"Echo failed: {response.error}")

        logger.info("Calling EchoMalloc...")
        response, echo_msg = device_service.echo_malloc(msg=b"Hello malloc!" * 100)
        if response.success and echo_msg is not None:
            logger.info(f"EchoMalloc response: {len(echo_msg.msg)}")
        else:
            logger.error(f"EchoMalloc failed: {response.error}")

        # Set LED
        logger.info("Calling SetLed(on=True)...")
        response, _ = device_service.set_led(on=True)
        if response.success:
            logger.info("LED turned ON")
        else:
            logger.error(f"SetLed failed: {response.error}")

        # Start sensor stream
        logger.info("Calling StartSensorStream...")
        response = device_service.start_sensor_stream()
        if response.success:
            logger.info("Sensor stream started")
        else:
            logger.error(f"StartSensorStream failed: {response.error}")

        # Wait and receive telemetry
        logger.info("Receiving telemetry for 10 seconds with LED on/off async...")
        for i in range(10):
            time.sleep(0.5)
            device_service.set_led(on=False)
            time.sleep(0.5)
            device_service.set_led(on=True)

        # Stop sensor stream
        logger.info("Calling StopSensorStream...")
        response = device_service.stop_sensor_stream()
        if response.success:
            logger.info("Sensor stream stopped")

        # Turn LED off
        logger.info("Calling SetLed(on=False)...")
        response, _ = device_service.set_led(on=False)
        if response.success:
            logger.info("LED turned OFF")

        # Cleanup
        telemetry.unsubscribe_all()
        logger.info("Unsubscribed from all topics")

    finally:
        session.close()
        logger.info("Zenoh session closed")


if __name__ == "__main__":
    main()
