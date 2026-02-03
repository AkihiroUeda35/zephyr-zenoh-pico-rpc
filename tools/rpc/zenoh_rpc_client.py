"""
Zenoh RPC Client - Low-level transport for RPC over Zenoh.
"""

import logging
from dataclasses import dataclass
from typing import Callable, Optional

import zenoh

logger = logging.getLogger(__name__)


@dataclass
class RpcResult:
    """Result of an RPC call."""

    success: bool
    data: bytes
    error: Optional[str] = None


@dataclass
class RpcResponse:
    """Generic RPC response wrapper."""

    success: bool
    error: Optional[str] = None


class ZenohRpcClient:
    """Zenoh RPC client for Query/Queryable pattern."""

    def __init__(self, session: zenoh.Session, device_id: str):
        self.session = session
        self.device_id = device_id

    def set_device_id(self, device_id: str):
        """Set or clear the target device ID."""
        self.device_id = device_id

    def call(self, service_name: str, method_name: str, request_data: bytes, timeout_ms: int = 5000) -> RpcResult:
        """Synchronous RPC call."""
        if self.device_id:
            key_expr = f"{self.device_id}/rpc/{service_name}/{method_name}"
        else:
            key_expr = f"rpc/{service_name}/{method_name}"

        try:
            replies = self.session.get(key_expr, payload=request_data, timeout=timeout_ms / 1000.0)

            for reply in replies:
                if reply.ok:
                    return RpcResult(success=True, data=bytes(reply.ok.payload))
                else:
                    return RpcResult(success=False, data=b"", error=f"Reply error: {reply.err}")

            return RpcResult(success=False, data=b"", error="No reply received")

        except Exception as e:
            logger.error(f"RPC call failed: {e}")
            return RpcResult(success=False, data=b"", error=str(e))


class ZenohSubscriberClient:
    """Zenoh subscriber for Pub/Sub pattern."""

    def __init__(self, session: zenoh.Session):
        self.session = session
        self._subscribers: dict[str, zenoh.Subscriber] = {}

    def subscribe(self, key_expr: str, callback: Callable[[bytes], None]) -> str:
        """Subscribe to a topic."""

        def handler(sample: zenoh.Sample):
            callback(bytes(sample.payload))

        subscriber = self.session.declare_subscriber(key_expr, handler)
        sub_id = str(id(subscriber))
        self._subscribers[sub_id] = subscriber
        return sub_id

    def unsubscribe(self, sub_id: str):
        """Unsubscribe from a topic."""
        if sub_id in self._subscribers:
            self._subscribers[sub_id].undeclare()
            del self._subscribers[sub_id]

    def unsubscribe_all(self):
        """Unsubscribe from all topics."""
        for subscriber in self._subscribers.values():
            subscriber.undeclare()
        self._subscribers.clear()


class LogSubscriber:
    """
    Subscriber for standard device logs (raw string).
    Topic: {device_id}/log
    """

    def __init__(
        self, subscriber_client: ZenohSubscriberClient, device_id: str, logger: Optional[logging.Logger] = None
    ):
        self.sub_client = subscriber_client
        self.device_id = device_id
        self.logger = logger or logging.getLogger(__name__)
        self._sub_id: Optional[str] = None

    def subscribe(self, callback: Callable[[str], None]):
        """
        Subscribe to log messages.
        callback: function that receives the log message (str).
        """
        key_expr = f"{self.device_id}/log"
        self.logger.info(f"Subscribing to logs: {key_expr}")

        def handler(data: bytes):
            try:
                message = data.decode("utf-8")
                callback(message)
            except Exception as e:
                self.logger.error(f"Failed to decode log message: {e}")

        self._sub_id = self.sub_client.subscribe(key_expr, handler)

    def unsubscribe(self):
        """Stop subscribing to logs."""
        if self._sub_id:
            self.sub_client.unsubscribe(self._sub_id)
            self._sub_id = None
            self.logger.info("Unsubscribed from logs")
