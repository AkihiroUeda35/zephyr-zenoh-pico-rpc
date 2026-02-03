import sys
from google.protobuf.internal import decoder
from requests import request


def to_snake_case(name):
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def find_zenoh_key(request):
    for proto_file in request.proto_file:
        for ext in proto_file.extension:
            if ext.name.endswith("zenoh_key"):
                # sys.stderr.write(f"Found zenoh_key extension with field number {ext.number}\n")
                return ext.number
    return 50001


def get_option_value(options_obj, field_number):
    """
    Serialize the options object to bytes and extract the string value for the specified field_number.
    This is the only reliable way to obtain values of custom options that cannot be imported.
    """
    # 1. Force to bytes (the data is guaranteed to be here)
    data = options_obj.SerializeToString()

    position = 0
    size = len(data)

    while position < size:
        # Read tag (Field ID + Wire Type)
        (tag, position) = decoder._DecodeVarint32(data, position)

        current_field_number = tag >> 3
        wire_type = tag & 0x07

        # Found target field
        if current_field_number == field_number:
            if wire_type == 2:  # String / Bytes
                # Read length
                (length, position) = decoder._DecodeVarint32(data, position)
                # Extract the data slice
                value_bytes = data[position : position + length]
                return value_bytes.decode("utf-8")
            else:
                # Return None if the type is not Length Delimited (string)
                return None

        # If not the target, skip to the next tag according to wire type
        if wire_type == 0:  # Varint
            (temp, position) = decoder._DecodeVarint64(data, position)
        elif wire_type == 1:  # 64-bit
            position += 8
        elif wire_type == 2:  # Length Delimited
            (length, position) = decoder._DecodeVarint32(data, position)
            position += length
        elif wire_type == 5:  # 32-bit
            position += 4
        else:
            # Unexpected wire type: ignore and continue
            pass

    return None
