#!/usr/bin/env python3
import asyncio
import json
from datetime import datetime
from functools import partial
from google.protobuf.json_format import MessageToDict

from nicegui import app, ui

from . import service_client as service_client
from . import service_pb2 as pb
from .zenoh_rpc_client import ZenohSubscriberClient, LogSubscriber

def create_ui(zenoh_client, default_device_id='pico2w-001'):
    # Subscriber Client
    sub_client = ZenohSubscriberClient(zenoh_client.session)
    active_subs = []

    with ui.row().classes('w-full items-start flex-nowrap'):
        # --- Left Column: RPC Controls --- 
        with ui.column().classes('flex-grow p-2'):
            # --- Device ID Selection --- 
            with ui.card().classes('w-full mb-4'):
                with ui.row().classes('w-full items-center no-wrap'):
                    device_id_input = ui.input(label='Device ID', value=default_device_id).classes('flex-grow').bind_value(app.storage.user, 'device_id')
                    ui.button('Set', on_click=lambda: update_subscriptions()).classes('ml-2')
            # --- DeviceService Service --- 
            device_service_client = service_client.DeviceServiceClient(zenoh_client)

            with ui.card().classes('w-full mb-2'):
                ui.label('DeviceService').classes('text-xl font-semibold')
                with ui.grid(columns=3).classes('w-full gap-4'):
                    with ui.column().classes('w-full p-0'):
                        with ui.expansion('SetLed', icon='api').classes('w-full').bind_value(app.storage.user, 'DeviceService.SetLed.expansion'):
                            inputs_set_led = {}
                            with ui.column().classes('w-full gap-2 p-2'):
                                inputs_set_led['on'] = ui.switch('On').bind_value(app.storage.user, 'DeviceService.SetLed.on')
                            result_area_set_led = ui.markdown().classes('w-full mt-2 text-sm')

                            async def call_set_led():
                                zenoh_client.set_device_id(device_id_input.value)
                                result_area_set_led.set_content('⏳ Calling RPC...')
                                await asyncio.sleep(0.01) # Allow UI to update
                                kwargs = {}
                                kwargs['on'] = inputs_set_led['on'].value
                                call_func = partial(device_service_client.set_led, **kwargs)
                                call_result = await asyncio.get_running_loop().run_in_executor(None, call_func)
                                response, payload = call_result
                                if response.success:
                                    md_content = '##### ✅ Success\n\n'
                                    if payload:
                                        md_content += '```\n' + str(payload).strip() + '\n```'
                                    result_area_set_led.set_content(md_content)
                                else:
                                    md_content = f'##### ❌ Error\n\n{response.error}'
                                    result_area_set_led.set_content(md_content)

                            ui.button('Execute', on_click=call_set_led).classes('w-full mt-2')

                    with ui.column().classes('w-full p-0'):
                        with ui.expansion('Echo', icon='api').classes('w-full').bind_value(app.storage.user, 'DeviceService.Echo.expansion'):
                            inputs_echo = {}
                            with ui.column().classes('w-full gap-2 p-2'):
                                inputs_echo['msg'] = ui.input(label='Msg').classes('w-full').bind_value(app.storage.user, 'DeviceService.Echo.msg')
                            result_area_echo = ui.markdown().classes('w-full mt-2 text-sm')

                            async def call_echo():
                                zenoh_client.set_device_id(device_id_input.value)
                                result_area_echo.set_content('⏳ Calling RPC...')
                                await asyncio.sleep(0.01) # Allow UI to update
                                kwargs = {}
                                kwargs['msg'] = inputs_echo['msg'].value
                                call_func = partial(device_service_client.echo, **kwargs)
                                call_result = await asyncio.get_running_loop().run_in_executor(None, call_func)
                                response, payload = call_result
                                if response.success:
                                    md_content = '##### ✅ Success\n\n'
                                    if payload:
                                        md_content += '```\n' + str(payload).strip() + '\n```'
                                    result_area_echo.set_content(md_content)
                                else:
                                    md_content = f'##### ❌ Error\n\n{response.error}'
                                    result_area_echo.set_content(md_content)

                            ui.button('Execute', on_click=call_echo).classes('w-full mt-2')

                    with ui.column().classes('w-full p-0'):
                        with ui.expansion('EchoMalloc', icon='api').classes('w-full').bind_value(app.storage.user, 'DeviceService.EchoMalloc.expansion'):
                            inputs_echo_malloc = {}
                            with ui.column().classes('w-full gap-2 p-2'):
                                inputs_echo_malloc['msg'] = ui.input(label='Msg').classes('w-full').bind_value(app.storage.user, 'DeviceService.EchoMalloc.msg')
                            result_area_echo_malloc = ui.markdown().classes('w-full mt-2 text-sm')

                            async def call_echo_malloc():
                                zenoh_client.set_device_id(device_id_input.value)
                                result_area_echo_malloc.set_content('⏳ Calling RPC...')
                                await asyncio.sleep(0.01) # Allow UI to update
                                kwargs = {}
                                val_msg = inputs_echo_malloc['msg'].value
                                if val_msg.startswith('0x'):
                                    kwargs['msg'] = bytes.fromhex(val_msg[2:])
                                else:
                                    kwargs['msg'] = val_msg.encode('utf-8')
                                call_func = partial(device_service_client.echo_malloc, **kwargs)
                                call_result = await asyncio.get_running_loop().run_in_executor(None, call_func)
                                response, payload = call_result
                                if response.success:
                                    md_content = '##### ✅ Success\n\n'
                                    if payload:
                                        md_content += '```\n' + str(payload).strip() + '\n```'
                                    result_area_echo_malloc.set_content(md_content)
                                else:
                                    md_content = f'##### ❌ Error\n\n{response.error}'
                                    result_area_echo_malloc.set_content(md_content)

                            ui.button('Execute', on_click=call_echo_malloc).classes('w-full mt-2')

                    with ui.column().classes('w-full p-0'):
                        with ui.expansion('StartSensorStream', icon='api').classes('w-full').bind_value(app.storage.user, 'DeviceService.StartSensorStream.expansion'):
                            result_area_start_sensor_stream = ui.markdown().classes('w-full mt-2 text-sm')

                            async def call_start_sensor_stream():
                                zenoh_client.set_device_id(device_id_input.value)
                                result_area_start_sensor_stream.set_content('⏳ Calling RPC...')
                                await asyncio.sleep(0.01) # Allow UI to update
                                call_func = device_service_client.start_sensor_stream
                                call_result = await asyncio.get_running_loop().run_in_executor(None, call_func)
                                response, payload = call_result, None
                                if response.success:
                                    md_content = '##### ✅ Success\n\n'
                                    if payload:
                                        md_content += '```\n' + str(payload).strip() + '\n```'
                                    result_area_start_sensor_stream.set_content(md_content)
                                else:
                                    md_content = f'##### ❌ Error\n\n{response.error}'
                                    result_area_start_sensor_stream.set_content(md_content)

                            ui.button('Execute', on_click=call_start_sensor_stream).classes('w-full mt-2')

                    with ui.column().classes('w-full p-0'):
                        with ui.expansion('StopSensorStream', icon='api').classes('w-full').bind_value(app.storage.user, 'DeviceService.StopSensorStream.expansion'):
                            result_area_stop_sensor_stream = ui.markdown().classes('w-full mt-2 text-sm')

                            async def call_stop_sensor_stream():
                                zenoh_client.set_device_id(device_id_input.value)
                                result_area_stop_sensor_stream.set_content('⏳ Calling RPC...')
                                await asyncio.sleep(0.01) # Allow UI to update
                                call_func = device_service_client.stop_sensor_stream
                                call_result = await asyncio.get_running_loop().run_in_executor(None, call_func)
                                response, payload = call_result, None
                                if response.success:
                                    md_content = '##### ✅ Success\n\n'
                                    if payload:
                                        md_content += '```\n' + str(payload).strip() + '\n```'
                                    result_area_stop_sensor_stream.set_content(md_content)
                                else:
                                    md_content = f'##### ❌ Error\n\n{response.error}'
                                    result_area_stop_sensor_stream.set_content(md_content)

                            ui.button('Execute', on_click=call_stop_sensor_stream).classes('w-full mt-2')

                    with ui.column().classes('w-full p-0'):
                        with ui.expansion('ConfigureWifi', icon='api').classes('w-full').bind_value(app.storage.user, 'DeviceService.ConfigureWifi.expansion'):
                            inputs_configure_wifi = {}
                            with ui.column().classes('w-full gap-2 p-2'):
                                inputs_configure_wifi['ssid'] = ui.input(label='Ssid').classes('w-full').bind_value(app.storage.user, 'DeviceService.ConfigureWifi.ssid')
                                inputs_configure_wifi['password'] = ui.input(label='Password').classes('w-full')
                            result_area_configure_wifi = ui.markdown().classes('w-full mt-2 text-sm')

                            async def call_configure_wifi():
                                zenoh_client.set_device_id(device_id_input.value)
                                result_area_configure_wifi.set_content('⏳ Calling RPC...')
                                await asyncio.sleep(0.01) # Allow UI to update
                                kwargs = {}
                                kwargs['ssid'] = inputs_configure_wifi['ssid'].value
                                kwargs['password'] = inputs_configure_wifi['password'].value
                                call_func = partial(device_service_client.configure_wifi, **kwargs)
                                call_result = await asyncio.get_running_loop().run_in_executor(None, call_func)
                                response, payload = call_result, None
                                if response.success:
                                    md_content = '##### ✅ Success\n\n'
                                    if payload:
                                        md_content += '```\n' + str(payload).strip() + '\n```'
                                    result_area_configure_wifi.set_content(md_content)
                                else:
                                    md_content = f'##### ❌ Error\n\n{response.error}'
                                    result_area_configure_wifi.set_content(md_content)

                            ui.button('Execute', on_click=call_configure_wifi).classes('w-full mt-2')

        # --- Right Column: Logs & Telemetry --- 
        with ui.column().classes('w-[400px] p-2'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('Logs & Telemetry').classes('text-xl font-bold')
                ui.button('Clear', on_click=lambda: log_view.clear()).props('dense flat icon=delete')
            log_view = ui.log().classes('w-full h-[calc(100vh-100px)] bg-gray-900 text-white font-mono text-xs')

    def log_message(msg):
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        log_view.push(f'[{ts}] {msg}')

    # --- Subscription Logic --- 
    def update_subscriptions():
        # Clear existing subscriptions
        for sub in active_subs:
            if hasattr(sub, 'unsubscribe'): sub.unsubscribe()
            if hasattr(sub, 'unsubscribe_all'): sub.unsubscribe_all()
        active_subs.clear()
        log_view.clear()
        log_message(f'--- Subscribing to {device_id_input.value} ---')

        # 1. Device Logs
        log_sub = LogSubscriber(sub_client, device_id_input.value)
        log_sub.subscribe(lambda msg: log_message(f'[LOG] {msg}'))
        active_subs.append(log_sub)

        # 2. Telemetry
        tel_sub = service_client.TelemetrySubscriber(sub_client, device_id_input.value)
        def on_subscribe_sensor(data):
            try:
                data_dict = MessageToDict(data, preserving_proto_field_name=True)
                log_message(f'[TEL] SensorTelemetry:\n{json.dumps(data_dict, indent=2)}')
            except Exception as e:
                log_message(f'[ERR] Parse error: {e}')

        tel_sub.subscribe_sensor(on_subscribe_sensor)
        active_subs.append(tel_sub)

    # Hook up update
    device_id_input.on('change', update_subscriptions)
    # Initial subscription
    update_subscriptions()