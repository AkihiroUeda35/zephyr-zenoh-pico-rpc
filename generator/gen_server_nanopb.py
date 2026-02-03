#!/usr/bin/env python3
"""
Generator for Zenoh RPC nanopb server code from .proto files.
"""

import sys
import os
from google.protobuf.compiler import plugin_pb2 as plugin
from google.protobuf.descriptor_pb2 import FileDescriptorProto
from util import to_snake_case, get_option_value, find_zenoh_key


def get_nanopb_type_name(proto_package, msg_name):
    """Generate Nanopb C struct name from proto package and message name"""
    # Example: practice.rpc + LedRequest -> practice_rpc_LedRequest
    if not proto_package:
        return msg_name
    return f"{proto_package.replace('.', '_')}_{msg_name}"


def parse_options_file(proto_file_name, proto_paths):
    """
    Parse .options file to find messages with FT_POINTER fields.
    Returns a set of message names (without package prefix) that have FT_POINTER fields.
    """
    messages_with_pointers = set()

    # Try to find .options file in proto_paths
    options_filename = proto_file_name.replace(".proto", ".options")
    options_file = None

    # First try absolute path if proto_file_name is absolute
    if os.path.isabs(proto_file_name):
        candidate = proto_file_name.replace(".proto", ".options")
        if os.path.exists(candidate):
            options_file = candidate

    # Try the same directory as the proto file
    if not options_file:
        proto_dir = os.path.dirname(proto_file_name)
        if proto_dir:
            candidate = os.path.join(proto_dir, os.path.basename(options_filename))
            if os.path.exists(candidate):
                options_file = candidate

    # Then try proto_paths
    if not options_file:
        for path in proto_paths:
            candidate = os.path.join(path, options_filename)
            if os.path.exists(candidate):
                options_file = candidate
                break
            # Also try with basename only
            candidate = os.path.join(path, os.path.basename(options_filename))
            if os.path.exists(candidate):
                options_file = candidate
                break

    # Try just the basename in current directory
    if not options_file:
        candidate = os.path.basename(options_filename)
        if os.path.exists(candidate):
            options_file = candidate

    if not options_file:
        return messages_with_pointers

    try:
        with open(options_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Parse lines like: "practice.rpc.EchoRequestMalloc.msg type:FT_POINTER"
                if "type:FT_POINTER" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        # Extract message name (e.g., "practice.rpc.EchoRequestMalloc.msg" -> "EchoRequestMalloc")
                        field_path = parts[0]
                        msg_name = field_path.split(".")[-2] if "." in field_path else None
                        if msg_name:
                            messages_with_pointers.add(msg_name)
    except Exception as e:
        # If we can't read the file, just return empty set
        import sys

        print(f"Warning: Could not read .options file: {e}", file=sys.stderr)

    return messages_with_pointers


def generate_code(request, response):
    files_to_generate = set(request.file_to_generate)

    # Extract include paths from request parameter
    # protoc passes options like "-I/path/to/dir"
    proto_paths = []
    if hasattr(request, "parameter") and request.parameter:
        # Parse parameters: protoc passes plugin options as a single string
        # Format: "-I/path1 -I/path2" or "-I=/path1 -I=/path2"
        params = request.parameter.strip()
        if params:
            # Split by spaces, but handle paths with spaces (quoted)
            parts = params.split()
            for i, part in enumerate(parts):
                # Handle -I/path or -I=/path format
                if part.startswith("-I"):
                    path = part[2:]  # Remove -I prefix
                    if path.startswith("="):
                        path = path[1:]  # Remove = if present
                    if path:
                        proto_paths.append(path)
                # Handle -I /path format (space-separated)
                elif i > 0 and parts[i - 1] == "-I":
                    proto_paths.append(part)

    # Also try current directory
    proto_paths.append(".")

    for proto_file in request.proto_file:
        if proto_file.name not in files_to_generate:
            continue
        if "google/protobuf" in proto_file.name:
            continue

        package = proto_file.package

        # Parse .options file to find messages with FT_POINTER
        messages_with_pointers = parse_options_file(proto_file.name, proto_paths)

        # 1. Generate header file (.h)
        f_h = response.file.add()
        f_h.name = os.path.basename(proto_file.name).replace(".proto", "_server.h")

        # 2. Generate implementation file (.cpp)
        f_cpp = response.file.add()
        f_cpp.name = os.path.basename(proto_file.name).replace(".proto", "_server.cpp")

        # Determine namespace (practice.rpc -> practice::rpc)
        cpp_namespace = package.replace(".", "::")
        guard_name = f_h.name.upper().replace(".", "_")

        # --- Generate header content ---
        h_content = []
        h_content.append(f"#ifndef {guard_name}")
        h_content.append(f"#define {guard_name}")
        h_content.append("")
        h_content.append('#include "zenoh_rpc_channel.h"')
        h_content.append(f'#include "{os.path.basename(proto_file.name).replace(".proto", ".pb.h")}"')  # Nanopb header
        h_content.append("")

        # Emit #define for messages that have the custom zenoh_key option
        zenoh_key_value = find_zenoh_key(request)
        for msg in proto_file.message_type:
            try:
                zenoh_key = get_option_value(msg.options, zenoh_key_value)
            except Exception:
                zenoh_key = None
            if zenoh_key:
                pkg_prefix = package.replace(".", "_").upper() if package else ""
                macro_name = f"{pkg_prefix + '_' if pkg_prefix else ''}{to_snake_case(msg.name).upper()}_ZENOH_KEY"
                h_content.append(f'#define {macro_name} "{zenoh_key}"')
        if any(get_option_value(m.options, zenoh_key_value) for m in proto_file.message_type):
            h_content.append("")

        h_content.append(f"namespace {cpp_namespace} {{")
        h_content.append("")

        # Service Interface definition
        for service in proto_file.service:
            h_content.append(f"// Interface for {service.name}")
            h_content.append(f"class {service.name} {{")
            h_content.append(" public:")
            h_content.append(f"  virtual ~{service.name}() = default;")

            for method in service.method:
                req_type = get_nanopb_type_name(package, method.input_type.split(".")[-1])
                res_type = get_nanopb_type_name(package, method.output_type.split(".")[-1])
                h_content.append(
                    f"  virtual zenoh_rpc::RpcStatus {method.name}(const {req_type}& req, {res_type}* resp) = 0;"
                )

            h_content.append("};")
            h_content.append("")

            # Server Class definition
            h_content.append(f"class {service.name}Server {{")
            h_content.append(" public:")
            h_content.append(f"  {service.name}Server(zenoh_rpc::ZenohRpcChannel& channel, {service.name}& impl);")
            h_content.append("  bool register_handlers();")
            h_content.append("")
            h_content.append(" private:")
            h_content.append("  zenoh_rpc::ZenohRpcChannel& channel_;")
            h_content.append(f"  {service.name}& impl_;")
            h_content.append(f'  static constexpr const char* kServiceName = "{service.name}";')
            h_content.append("")

            # Handler method declarations
            for method in service.method:
                h_content.append(
                    f"  zenoh_rpc::RpcStatus handle_{method.name}(pb_istream_t* req_stream, pb_ostream_t* resp_stream);"
                )

            h_content.append("};")
            h_content.append("")

        h_content.append(f"}}  // namespace {cpp_namespace}")
        h_content.append(f"#endif  // {guard_name}")
        f_h.content = "\n".join(h_content)

        # --- Generate implementation file content ---
        c_content = []
        c_content.append(f'#include "{f_h.name}"')
        c_content.append("#include <pb_encode.h>")
        c_content.append("#include <pb_decode.h>")
        c_content.append("#include <pb_common.h>")
        c_content.append('#include "log_wrapper.h"')
        c_content.append("")
        # Module registration (create unique name from filename)
        module_name = os.path.basename(proto_file.name).replace(".proto", "_server").replace(".", "_")
        c_content.append("#ifdef __ZEPHYR__")
        c_content.append(f"LOG_MODULE_REGISTER({module_name}, LOG_LEVEL_INF);")
        c_content.append("#endif  // __ZEPHYR__")
        c_content.append("")
        c_content.append(f"namespace {cpp_namespace} {{")
        c_content.append("")

        for service in proto_file.service:
            # Constructor
            c_content.append(
                f"{service.name}Server::{service.name}Server(zenoh_rpc::ZenohRpcChannel& channel, {service.name}& impl)"
            )
            c_content.append("    : channel_(channel), impl_(impl) {}")
            c_content.append("")

            # register_handlers
            c_content.append(f"bool {service.name}Server::register_handlers() {{")
            c_content.append("  bool success = true;")
            c_content.append("")

            for method in service.method:
                c_content.append(f"  // {method.name}")
                c_content.append(f"  success &= channel_.register_handler(")
                c_content.append(f'      kServiceName, "{method.name}",')
                c_content.append(f"      [this](pb_istream_t* req_stream, pb_ostream_t* resp_stream) {{")
                c_content.append(f"        return handle_{method.name}(req_stream, resp_stream);")
                c_content.append(f"      }});")
                c_content.append("")

            c_content.append("  if (success) {")
            c_content.append(f'    LOG_INF("All {service.name} handlers registered");')
            c_content.append("  } else {")
            c_content.append(f'    LOG_ERR("Failed to register some {service.name} handlers");')
            c_content.append("  }")
            c_content.append("  return success;")
            c_content.append("}")
            c_content.append("")

            # Implementation of each handler
            for method in service.method:
                req_type = get_nanopb_type_name(package, method.input_type.split(".")[-1])
                res_type = get_nanopb_type_name(package, method.output_type.split(".")[-1])

                # Check if request or response has FT_POINTER fields
                req_msg_name = method.input_type.split(".")[-1]
                res_msg_name = method.output_type.split(".")[-1]
                req_needs_release = req_msg_name in messages_with_pointers
                res_needs_release = res_msg_name in messages_with_pointers

                c_content.append(f"zenoh_rpc::RpcStatus {service.name}Server::handle_{method.name}(")
                c_content.append("    pb_istream_t* req_stream, pb_ostream_t* resp_stream) {")

                # Decode
                c_content.append("  // Decode request")
                c_content.append(f"  {req_type} request = {req_type}_init_zero;")
                c_content.append(f"  if (!pb_decode(req_stream, {req_type}_fields, &request)) {{")
                c_content.append(f'    LOG_ERR("Failed to decode {method.input_type.split(".")[-1]}");')
                c_content.append("    return zenoh_rpc::RpcStatus::DECODE_ERROR;")
                c_content.append("  }")
                c_content.append("")

                # Call Implementation
                c_content.append("  // Call implementation")
                c_content.append(f"  {res_type} response = {res_type}_init_zero;")
                c_content.append(f"  zenoh_rpc::RpcStatus status = impl_.{method.name}(request, &response);")
                c_content.append("  if (status != zenoh_rpc::RpcStatus::OK) {")
                if req_needs_release:
                    c_content.append(f"    pb_release({req_type}_fields, &request);")
                c_content.append("    return status;")
                c_content.append("  }")
                c_content.append("")

                # Encode
                c_content.append("  // Encode response directly to stream (zero-copy)")
                c_content.append(f"  if (!pb_encode(resp_stream, {res_type}_fields, &response)) {{")
                c_content.append(f'    LOG_ERR("Failed to encode {method.output_type.split(".")[-1]}");')
                if req_needs_release:
                    c_content.append(f"    pb_release({req_type}_fields, &request);")
                if res_needs_release:
                    c_content.append(f"    pb_release({res_type}_fields, &response);")
                c_content.append("    return zenoh_rpc::RpcStatus::ENCODE_ERROR;")
                c_content.append("  }")
                c_content.append("")

                # Release allocated memory if needed
                if req_needs_release or res_needs_release:
                    c_content.append("  // Release allocated memory")
                    if req_needs_release:
                        c_content.append(f"  pb_release({req_type}_fields, &request);")
                    if res_needs_release:
                        c_content.append(f"  pb_release({res_type}_fields, &response);")
                    c_content.append("")

                c_content.append("  return zenoh_rpc::RpcStatus::OK;")
                c_content.append("}")
                c_content.append("")

        c_content.append(f"}}  // namespace {cpp_namespace}")
        f_cpp.content = "\n".join(c_content)


if __name__ == "__main__":
    data = sys.stdin.buffer.read()
    request = plugin.CodeGeneratorRequest()
    request.ParseFromString(data)
    response = plugin.CodeGeneratorResponse()
    generate_code(request, response)
    sys.stdout.buffer.write(response.SerializeToString())
