from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor
ZENOH_KEY_FIELD_NUMBER: _ClassVar[int]
zenoh_key: _descriptor.FieldDescriptor

class WifiSettings(_message.Message):
    __slots__ = ("ssid", "password")
    SSID_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    ssid: str
    password: str
    def __init__(self, ssid: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class LedRequest(_message.Message):
    __slots__ = ("on",)
    ON_FIELD_NUMBER: _ClassVar[int]
    on: bool
    def __init__(self, on: bool = ...) -> None: ...

class LedResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class EchoRequest(_message.Message):
    __slots__ = ("msg",)
    MSG_FIELD_NUMBER: _ClassVar[int]
    msg: str
    def __init__(self, msg: _Optional[str] = ...) -> None: ...

class EchoResponse(_message.Message):
    __slots__ = ("msg",)
    MSG_FIELD_NUMBER: _ClassVar[int]
    msg: str
    def __init__(self, msg: _Optional[str] = ...) -> None: ...

class EchoRequestMalloc(_message.Message):
    __slots__ = ("msg",)
    MSG_FIELD_NUMBER: _ClassVar[int]
    msg: bytes
    def __init__(self, msg: _Optional[bytes] = ...) -> None: ...

class EchoResponseMalloc(_message.Message):
    __slots__ = ("msg",)
    MSG_FIELD_NUMBER: _ClassVar[int]
    msg: bytes
    def __init__(self, msg: _Optional[bytes] = ...) -> None: ...

class SensorRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SensorTelemetry(_message.Message):
    __slots__ = ("temperature", "humidity")
    TEMPERATURE_FIELD_NUMBER: _ClassVar[int]
    HUMIDITY_FIELD_NUMBER: _ClassVar[int]
    temperature: float
    humidity: float
    def __init__(self, temperature: _Optional[float] = ..., humidity: _Optional[float] = ...) -> None: ...

class Empty(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...
