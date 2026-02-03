#!/usr/bin/env python3
"""
Generator for Zenoh RPC Python client code from .proto files.
"""

import sys
import os
from google.protobuf.compiler import plugin_pb2 as plugin
from google.protobuf.descriptor_pb2 import FieldDescriptorProto
from util import get_option_value, to_snake_case, find_zenoh_key


TYPE_MAPPING = {
    FieldDescriptorProto.TYPE_DOUBLE: "float",
    FieldDescriptorProto.TYPE_FLOAT: "float",
    FieldDescriptorProto.TYPE_INT32: "int",
    FieldDescriptorProto.TYPE_INT64: "int",
    FieldDescriptorProto.TYPE_UINT32: "int",
    FieldDescriptorProto.TYPE_UINT64: "int",
    FieldDescriptorProto.TYPE_BOOL: "bool",
    FieldDescriptorProto.TYPE_STRING: "str",
    FieldDescriptorProto.TYPE_BYTES: "bytes",
}


def get_message_map(proto_file):
    package = proto_file.package
    msg_map = {}
    for msg in proto_file.message_type:
        full_name = f".{package}.{msg.name}" if package else f".{msg.name}"
        msg_map[full_name] = msg
    return msg_map


def generate_code(request, response):
    files_to_generate = set(request.file_to_generate)

    for proto_file in request.proto_file:
        if proto_file.name not in files_to_generate:
            continue
        if "google/protobuf" in proto_file.name:
            continue

        msg_map = get_message_map(proto_file)

        f = response.file.add()
        filename = os.path.basename(proto_file.name).replace(".proto", "_client.py")
        f.name = filename

        pb_import_path = proto_file.name.replace(".proto", "_pb2").replace("/", ".")

        content = []
        content.append("import logging")
        content.append("from dataclasses import dataclass")
        content.append("from typing import Callable, Optional, Tuple, Union, List")
        content.append("from .zenoh_rpc_client import ZenohRpcClient, ZenohSubscriberClient, RpcResult, RpcResponse")
        content.append(f"from . import {pb_import_path.split('.')[-1]} as pb")
        content.append("")
        content.append("")

        # ---------------------------------------------------------
        # 1. RPC Client
        # ---------------------------------------------------------
        for service in proto_file.service:
            content.append(f"class {service.name}Client:")
            content.append(f'    SERVICE_NAME = "{service.name}"')
            content.append("")
            content.append("    def __init__(self, rpc_client: ZenohRpcClient):")
            content.append("        self.rpc_client = rpc_client")
            content.append("")

            for method in service.method:
                method_snake = to_snake_case(method.name)
                req_cls_name = method.input_type.split(".")[-1]

                arg_list_str = f"self, request: Optional[pb.{req_cls_name}] = None"
                input_msg = msg_map.get(method.input_type)
                field_assigns = []

                if input_msg and len(input_msg.field) > 0:
                    arg_list_str += ", *"
                    for field in input_msg.field:
                        py_type = TYPE_MAPPING.get(field.type, "Any")
                        arg_list_str += f", {field.name}: Optional[{py_type}] = None"
                        field_assigns.append(f"{field.name}={field.name}")

                is_empty = method.output_type.endswith("Empty")
                ret_type = (
                    "RpcResponse"
                    if is_empty
                    else f"tuple[RpcResponse, Optional[pb.{method.output_type.split('.')[-1]}]]"
                )

                content.append(f"    def {method_snake}({arg_list_str}) -> {ret_type}:")
                content.append(f'        """{method.name} RPC call."""')
                content.append("        if request is None:")
                if field_assigns:
                    assign_str = ", ".join(field_assigns)
                    content.append(f"            request = pb.{req_cls_name}({assign_str})")
                else:
                    content.append(f"            request = pb.{req_cls_name}()")

                content.append("")
                content.append(
                    f'        result = self.rpc_client.call(self.SERVICE_NAME, "{method.name}", request.SerializeToString())'
                )

                content.append("        if result.success:")
                if is_empty:
                    content.append("            return RpcResponse(success=True)")
                    content.append("        return RpcResponse(success=False, error=result.error)")
                else:
                    resp_cls = method.output_type.split(".")[-1]
                    content.append(f"            response = pb.{resp_cls}()")
                    content.append("            response.ParseFromString(result.data)")
                    content.append("            return RpcResponse(success=True), response")
                    content.append("        return RpcResponse(success=False, error=result.error), None")
                content.append("")

        # ---------------------------------------------------------
        # 2. Telemetry Subscriber
        # ---------------------------------------------------------
        telemetry_msgs = [m for m in proto_file.message_type if m.name.endswith("Telemetry")]

        if telemetry_msgs:
            content.append("class TelemetrySubscriber:")
            content.append('    """Subscriber for telemetry data from device."""')
            content.append("")
            content.append(
                "    def __init__(self, sub_client: ZenohSubscriberClient, device_id: str, logger: Optional[logging.Logger] = None):"
            )
            content.append("        self.sub_client = sub_client")
            content.append("        self.device_id = device_id")
            content.append("        self._sub_ids: List[str] = []")
            content.append("        self.logger = logger or logging.getLogger(__name__)")
            content.append("")

            for msg in telemetry_msgs:
                base_name = msg.name.replace("Telemetry", "")
                snake_name = to_snake_case(base_name)

                # Extract zenoh_key from custom options (field number 50001)
                zenoh_key = get_option_value(msg.options, find_zenoh_key(request))
                # Use default key if not specified
                if not zenoh_key:
                    zenoh_key = f"/telemetry/{snake_name}"

                type_hint = f"Callable[[pb.{msg.name}], None]"
                content.append(f"    def subscribe_{snake_name}(self, callback: {type_hint}):")
                content.append(f'        """Subscribe to {snake_name} telemetry."""')
                content.append(f'        key_expr = f"{{self.device_id}}{zenoh_key}"')
                content.append(f'        self.logger.info(f"Subscribing to: {{key_expr}}")')
                content.append("")
                content.append(f"        def handler(data: bytes):")
                content.append(f"            try:")
                content.append(f"                payload = pb.{msg.name}()")
                content.append(f"                payload.ParseFromString(data)")
                content.append(f"                callback(payload)")
                content.append(f"            except Exception as e:")
                content.append(f'                self.logger.error(f"Failed to parse {msg.name}: {{e}}")')
                content.append("")
                content.append(f"        sub_id = self.sub_client.subscribe(key_expr, handler)")
                content.append(f"        self._sub_ids.append(sub_id)")
                content.append("")

            content.append("    def unsubscribe_all(self):")
            content.append('        """Unsubscribe from all topics."""')
            content.append("        for sid in self._sub_ids:")
            content.append("            self.sub_client.unsubscribe(sid)")
            content.append("        self._sub_ids.clear()")
            content.append('        self.logger.info("Unsubscribed from all telemetry topics")')
            content.append("")

        f.content = "\n".join(content)


if __name__ == "__main__":
    data = sys.stdin.buffer.read()
    request = plugin.CodeGeneratorRequest()
    request.ParseFromString(data)
    response = plugin.CodeGeneratorResponse()
    generate_code(request, response)
    sys.stdout.buffer.write(response.SerializeToString())
