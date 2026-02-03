import logging
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Union, List
from .zenoh_rpc_client import ZenohRpcClient, ZenohSubscriberClient, RpcResult, RpcResponse
from . import service_pb2 as pb


class DeviceServiceClient:
    SERVICE_NAME = "DeviceService"

    def __init__(self, rpc_client: ZenohRpcClient):
        self.rpc_client = rpc_client

    def set_led(self, request: Optional[pb.LedRequest] = None, *, on: Optional[bool] = None) -> tuple[RpcResponse, Optional[pb.LedResponse]]:
        """SetLed RPC call."""
        if request is None:
            request = pb.LedRequest(on=on)

        result = self.rpc_client.call(self.SERVICE_NAME, "SetLed", request.SerializeToString())
        if result.success:
            response = pb.LedResponse()
            response.ParseFromString(result.data)
            return RpcResponse(success=True), response
        return RpcResponse(success=False, error=result.error), None

    def echo(self, request: Optional[pb.EchoRequest] = None, *, msg: Optional[str] = None) -> tuple[RpcResponse, Optional[pb.EchoResponse]]:
        """Echo RPC call."""
        if request is None:
            request = pb.EchoRequest(msg=msg)

        result = self.rpc_client.call(self.SERVICE_NAME, "Echo", request.SerializeToString())
        if result.success:
            response = pb.EchoResponse()
            response.ParseFromString(result.data)
            return RpcResponse(success=True), response
        return RpcResponse(success=False, error=result.error), None

    def echo_malloc(self, request: Optional[pb.EchoRequestMalloc] = None, *, msg: Optional[bytes] = None) -> tuple[RpcResponse, Optional[pb.EchoResponseMalloc]]:
        """EchoMalloc RPC call."""
        if request is None:
            request = pb.EchoRequestMalloc(msg=msg)

        result = self.rpc_client.call(self.SERVICE_NAME, "EchoMalloc", request.SerializeToString())
        if result.success:
            response = pb.EchoResponseMalloc()
            response.ParseFromString(result.data)
            return RpcResponse(success=True), response
        return RpcResponse(success=False, error=result.error), None

    def start_sensor_stream(self, request: Optional[pb.SensorRequest] = None) -> RpcResponse:
        """StartSensorStream RPC call."""
        if request is None:
            request = pb.SensorRequest()

        result = self.rpc_client.call(self.SERVICE_NAME, "StartSensorStream", request.SerializeToString())
        if result.success:
            return RpcResponse(success=True)
        return RpcResponse(success=False, error=result.error)

    def stop_sensor_stream(self, request: Optional[pb.Empty] = None) -> RpcResponse:
        """StopSensorStream RPC call."""
        if request is None:
            request = pb.Empty()

        result = self.rpc_client.call(self.SERVICE_NAME, "StopSensorStream", request.SerializeToString())
        if result.success:
            return RpcResponse(success=True)
        return RpcResponse(success=False, error=result.error)

    def configure_wifi(self, request: Optional[pb.WifiSettings] = None, *, ssid: Optional[str] = None, password: Optional[str] = None) -> RpcResponse:
        """ConfigureWifi RPC call."""
        if request is None:
            request = pb.WifiSettings(ssid=ssid, password=password)

        result = self.rpc_client.call(self.SERVICE_NAME, "ConfigureWifi", request.SerializeToString())
        if result.success:
            return RpcResponse(success=True)
        return RpcResponse(success=False, error=result.error)

class TelemetrySubscriber:
    """Subscriber for telemetry data from device."""

    def __init__(self, sub_client: ZenohSubscriberClient, device_id: str, logger: Optional[logging.Logger] = None):
        self.sub_client = sub_client
        self.device_id = device_id
        self._sub_ids: List[str] = []
        self.logger = logger or logging.getLogger(__name__)

    def subscribe_sensor(self, callback: Callable[[pb.SensorTelemetry], None]):
        """Subscribe to sensor telemetry."""
        key_expr = f"{self.device_id}/telemetry/sensor"
        self.logger.info(f"Subscribing to: {key_expr}")

        def handler(data: bytes):
            try:
                payload = pb.SensorTelemetry()
                payload.ParseFromString(data)
                callback(payload)
            except Exception as e:
                self.logger.error(f"Failed to parse SensorTelemetry: {e}")

        sub_id = self.sub_client.subscribe(key_expr, handler)
        self._sub_ids.append(sub_id)

    def unsubscribe_all(self):
        """Unsubscribe from all topics."""
        for sid in self._sub_ids:
            self.sub_client.unsubscribe(sid)
        self._sub_ids.clear()
        self.logger.info("Unsubscribed from all telemetry topics")
