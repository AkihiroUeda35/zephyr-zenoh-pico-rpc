#!/usr/bin/env python3
"""
Generator for NiceGUI Python client code from .proto files.
"""

import sys
import os
from google.protobuf.compiler import plugin_pb2 as plugin
from google.protobuf.descriptor_pb2 import FieldDescriptorProto
from util import to_snake_case


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
    """Creates a map of fully qualified message names to their descriptors."""
    package = proto_file.package
    msg_map = {}
    for msg in proto_file.message_type:
        full_name = "." + package + "." + msg.name if package else "." + msg.name
        msg_map[full_name] = msg
    return msg_map


def generate_code(request, response):
    """Generates the NiceGUI application code."""
    files_to_generate = set(request.file_to_generate)

    for proto_file in request.proto_file:
        if proto_file.name not in files_to_generate or "google/protobuf" in proto_file.name:
            continue

        msg_map = get_message_map(proto_file)
        proto_filename_base = os.path.basename(proto_file.name).replace(".proto", "")

        f = response.file.add()
        f.name = "service_gui.py"

        content = [
            "#!/usr/bin/env python3",
            "import asyncio",
            "import json",
            "from datetime import datetime",
            "from functools import partial",
            "from google.protobuf.json_format import MessageToDict",
            "",
            "from nicegui import app, ui",
            "",
            "from . import " + proto_filename_base + "_client as service_client",
            "from . import " + proto_filename_base + "_pb2 as pb",
            "from .zenoh_rpc_client import ZenohSubscriberClient, LogSubscriber",
            "",
            "def create_ui(zenoh_client, default_device_id='pico2w-001'):",
            "    # Subscriber Client",
            "    sub_client = ZenohSubscriberClient(zenoh_client.session)",
            "    active_subs = []",
            "",
            "    with ui.row().classes('w-full items-start flex-nowrap'):",
            "        # --- Left Column: RPC Controls --- ",
            "        with ui.column().classes('flex-grow p-2'):",
            "            # --- Device ID Selection --- ",
            "            with ui.card().classes('w-full mb-4'):",
            "                with ui.row().classes('w-full items-center no-wrap'):",
            "                    device_id_input = ui.input(label='Device ID', value=default_device_id).classes('flex-grow').bind_value(app.storage.user, 'device_id')",
            "                    ui.button('Set', on_click=lambda: update_subscriptions()).classes('ml-2')",
        ]

        for service in proto_file.service:
            client_instance_name = to_snake_case(service.name) + "_client"
            content.extend(
                [
                    "            # --- " + service.name + " Service --- ",
                    "            "
                    + client_instance_name
                    + " = service_client."
                    + service.name
                    + "Client(zenoh_client)",
                    "",
                    "            with ui.card().classes('w-full mb-2'):",
                    "                ui.label('" + service.name + "').classes('text-xl font-semibold')",
                ]
            )

            content.append("                with ui.grid(columns=3).classes('w-full gap-4'):")

            for method in service.method:
                method_snake = to_snake_case(method.name)

                input_msg_def = msg_map.get(method.input_type)

                has_input = input_msg_def and len(input_msg_def.field) > 0

                content.append("                    with ui.column().classes('w-full p-0'):")

                content.append(
                    "                        with ui.expansion('"
                    + method.name
                    + "', icon='api').classes('w-full').bind_value(app.storage.user, '"
                    + service.name
                    + "."
                    + method.name
                    + ".expansion"
                    + "'):"
                )

                # Inputs

                if has_input:
                    content.append("                            inputs_" + method_snake + " = {}")

                    content.append("                            with ui.column().classes('w-full gap-2 p-2'):")

                    for field in input_msg_def.field:
                        field_type = TYPE_MAPPING.get(field.type, "str")

                        label = field.name.replace("_", " ").capitalize()

                        bind_suffix = ""

                        if "password" not in field.name.lower():
                            bind_suffix = (
                                ".bind_value(app.storage.user, '"
                                + service.name
                                + "."
                                + method.name
                                + "."
                                + field.name
                                + "')"
                            )

                        if field_type == "bool":
                            content.append(
                                "                                inputs_"
                                + method_snake
                                + "['"
                                + field.name
                                + "'] = ui.switch('"
                                + label
                                + "')"
                                + bind_suffix
                            )

                        elif field_type in ["int", "float"]:
                            content.append(
                                "                                inputs_"
                                + method_snake
                                + "['"
                                + field.name
                                + "'] = ui.number(label='"
                                + label
                                + "', value=0, format='%.2f').classes('w-full')"
                                + bind_suffix
                            )

                        else:
                            content.append(
                                "                                inputs_"
                                + method_snake
                                + "['"
                                + field.name
                                + "'] = ui.input(label='"
                                + label
                                + "').classes('w-full')"
                                + bind_suffix
                            )

                # Result Area Definition (placeholder)

                content.append(
                    "                            result_area_"
                    + method_snake
                    + " = ui.markdown().classes('w-full mt-2 text-sm')"
                )

                # Async Function Definition

                content.extend(
                    [
                        "",
                        "                            async def call_" + method_snake + "():",
                        "                                zenoh_client.set_device_id(device_id_input.value)",
                        "                                result_area_"
                        + method_snake
                        + ".set_content('⏳ Calling RPC...')",
                        "                                await asyncio.sleep(0.01) # Allow UI to update",
                    ]
                )

                if has_input:
                    content.append("                                kwargs = {}")

                    for field in input_msg_def.field:
                        field_type = TYPE_MAPPING.get(field.type, "str")

                        if field_type in ["int", "float"]:
                            content.extend(
                                [
                                    "                                try:",
                                    "                                    kwargs['"
                                    + field.name
                                    + "'] = "
                                    + field_type
                                    + "(inputs_"
                                    + method_snake
                                    + "['"
                                    + field.name
                                    + "'].value)",
                                    "                                except (ValueError, TypeError):",
                                    "                                    result_area_"
                                    + method_snake
                                    + ".set_content('❌ Invalid input for `"
                                    + field.name
                                    + "`')",
                                    "                                    return",
                                ]
                            )

                        elif field_type == "bytes":
                            content.extend(
                                [
                                    "                                val_"
                                    + field.name
                                    + " = inputs_"
                                    + method_snake
                                    + "['"
                                    + field.name
                                    + "'].value",
                                    "                                if val_" + field.name + ".startswith('0x'):",
                                    "                                    kwargs['"
                                    + field.name
                                    + "'] = bytes.fromhex(val_"
                                    + field.name
                                    + "[2:])",
                                    "                                else:",
                                    "                                    kwargs['"
                                    + field.name
                                    + "'] = val_"
                                    + field.name
                                    + ".encode('utf-8')",
                                ]
                            )

                        else:
                            content.append(
                                "                                kwargs['"
                                + field.name
                                + "'] = inputs_"
                                + method_snake
                                + "['"
                                + field.name
                                + "'].value"
                            )

                    content.append(
                        "                                call_func = partial("
                        + client_instance_name
                        + "."
                        + method_snake
                        + ", **kwargs)"
                    )

                else:
                    content.append(
                        "                                call_func = " + client_instance_name + "." + method_snake
                    )

                is_output_empty = method.output_type.endswith("Empty")

                content.append(
                    "                                call_result = await asyncio.get_running_loop().run_in_executor(None, call_func)"
                )

                if is_output_empty:
                    content.append("                                response, payload = call_result, None")

                else:
                    content.append("                                response, payload = call_result")

                content.extend(
                    [
                        "                                if response.success:",
                        "                                    md_content = '##### ✅ Success\\n\\n'",
                        "                                    if payload:",
                        "                                        md_content += '```\\n' + str(payload).strip() + '\\n```'",
                        "                                    result_area_" + method_snake + ".set_content(md_content)",
                        "                                else:",
                        "                                    md_content = f'##### ❌ Error\\n\\n{response.error}'",
                        "                                    result_area_" + method_snake + ".set_content(md_content)",
                        "",
                        "                            ui.button('Execute', on_click=call_"
                        + method_snake
                        + ").classes('w-full mt-2')",
                        "",
                    ]
                )

        # End of Left Column and Right Column & Subscription Logic
        content.extend(
            [
                "        # --- Right Column: Logs & Telemetry --- ",
                "        with ui.column().classes('w-[400px] p-2'):",
                "            with ui.row().classes('w-full items-center justify-between'):",
                "                ui.label('Logs & Telemetry').classes('text-xl font-bold')",
                "                ui.button('Clear', on_click=lambda: log_view.clear()).props('dense flat icon=delete')",
                "            log_view = ui.log().classes('w-full h-[calc(100vh-100px)] bg-gray-900 text-white font-mono text-xs')",
                "",
                "    def log_message(msg):",
                "        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]",
                "        log_view.push(f'[{ts}] {msg}')",
                "",
                "    # --- Subscription Logic --- ",
                "    def update_subscriptions():",
                "        # Clear existing subscriptions",
                "        for sub in active_subs:",
                "            if hasattr(sub, 'unsubscribe'): sub.unsubscribe()",
                "            if hasattr(sub, 'unsubscribe_all'): sub.unsubscribe_all()",
                "        active_subs.clear()",
                "        log_view.clear()",
                "        log_message(f'--- Subscribing to {device_id_input.value} ---')",
                "",
                "        # 1. Device Logs",
                "        log_sub = LogSubscriber(sub_client, device_id_input.value)",
                "        log_sub.subscribe(lambda msg: log_message(f'[LOG] {msg}'))",
                "        active_subs.append(log_sub)",
                "",
            ]
        )

        # Telemetry Logic
        telemetry_msgs = [msg for msg in proto_file.message_type if msg.name.endswith("Telemetry")]
        if telemetry_msgs:
            content.append("        # 2. Telemetry")
            content.append("        tel_sub = service_client.TelemetrySubscriber(sub_client, device_id_input.value)")
            for msg in telemetry_msgs:
                base_name = msg.name.replace("Telemetry", "")
                method_name = "subscribe_" + to_snake_case(base_name)
                content.append(f"        def on_{method_name}(data):")
                content.append(f"            try:")
                content.append(f"                data_dict = MessageToDict(data, preserving_proto_field_name=True)")
                content.append(
                    f"                log_message(f'[TEL] {msg.name}:\\n{{json.dumps(data_dict, indent=2)}}')"
                )
                content.append(f"            except Exception as e:")
                content.append(f"                log_message(f'[ERR] Parse error: {{e}}')")
                content.append("")
                content.append(f"        tel_sub.{method_name}(on_{method_name})")
            content.append("        active_subs.append(tel_sub)")

        content.extend(
            [
                "",
                "    # Hook up update",
                "    device_id_input.on('change', update_subscriptions)",
                "    # Initial subscription",
                "    update_subscriptions()",
            ]
        )

        f.content = "\n".join(content)


if __name__ == "__main__":
    data = sys.stdin.buffer.read()
    request = plugin.CodeGeneratorRequest()
    request.ParseFromString(data)
    response = plugin.CodeGeneratorResponse()
    generate_code(request, response)
    sys.stdout.buffer.write(response.SerializeToString())
