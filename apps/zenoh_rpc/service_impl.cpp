// Device Service Implementation
#include "service_impl.h"

#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/logging/log.h>

#include <cstring>

#include "wifi/wifi_manager.h"

LOG_MODULE_REGISTER(device_service_impl, LOG_LEVEL_INF);

#define LED0_NODE DT_ALIAS(led0)
const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(LED0_NODE, gpios);

#define DHT22_NODE DT_ALIAS(dht0)
const struct device* const dht22_dev = DEVICE_DT_GET(DHT22_NODE);

namespace practice::rpc {

zenoh_rpc::RpcStatus DeviceServiceImpl::SetLed(
    const practice_rpc_LedRequest& request,
    practice_rpc_LedResponse* response) {
  LOG_INF("SetLed: on=%d", request.on);

  if (log_pub_) {
    log_pub_->log_info("LED set to %s", request.on ? "ON" : "OFF");
  }
  if (request.on) {
    LOG_INF("Turning LED ON");
    gpio_pin_set_dt(&led, 1);

  } else {
    LOG_INF("Turning LED OFF");
    gpio_pin_set_dt(&led, 0);
  }
  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceImpl::Echo(
    const practice_rpc_EchoRequest& request,
    practice_rpc_EchoResponse* response) {
  LOG_INF("Echo: msg=%s", request.msg);

  // Echo back the message
  strncpy(response->msg, request.msg, sizeof(response->msg) - 1);
  response->msg[sizeof(response->msg) - 1] = '\0';

  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceImpl::EchoMalloc(
    const practice_rpc_EchoRequestMalloc& request,
    practice_rpc_EchoResponseMalloc* response) {
  LOG_INF("EchoMalloc: msg length=%d", (int)request.msg->size);

  // Echo back the message
  response->msg = (pb_bytes_array_t*)malloc(
      sizeof(pb_size_t) +
      request.msg->size * sizeof(uint8_t));  // allocation needed first
  if (response->msg == NULL) {
    LOG_ERR("EchoMalloc: Memory allocation failed");
    return zenoh_rpc::RpcStatus::TRANSPORT_ERROR;
  }
  response->msg->size = request.msg->size;
  memcpy(response->msg->bytes, request.msg->bytes, (size_t)request.msg->size);

  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceImpl::StartSensorStream(
    const practice_rpc_SensorRequest& request, practice_rpc_Empty* response) {
  LOG_INF("StartSensorStream");
  streaming_enabled_ = true;
  if (log_pub_) {
    log_pub_->log_info("Sensor streaming started");
  }
  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceImpl::StopSensorStream(
    const practice_rpc_Empty& request, practice_rpc_Empty* response) {
  LOG_INF("StopSensorStream");
  streaming_enabled_ = false;
  if (log_pub_) {
    log_pub_->log_info("Sensor streaming stopped");
  }
  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceImpl::ConfigureWifi(
    const practice_rpc_WifiSettings& request, practice_rpc_Empty* response) {
  LOG_INF("ConfigureWifi: ssid=%s", request.ssid);

  if (log_pub_) {
    log_pub_->log_info("WiFi configured: %s", request.ssid);
  }
  // Save credentials to NVS and connect
  wifi::WifiManager& wifi_mgr = wifi::get_wifi_manager();
  if (!wifi_mgr.configure_and_connect(request.ssid, request.password)) {
    LOG_ERR("Failed to configure Wi-Fi");
    return zenoh_rpc::RpcStatus::TRANSPORT_ERROR;
  }
  return zenoh_rpc::RpcStatus::OK;
}

void DeviceServiceImpl::publish_sensor_data() {
  if (!streaming_enabled_ || !sensor_pub_) {
    return;
  }
  // Check if DHT22 device is ready
  if (!device_is_ready(dht22_dev)) {
    LOG_ERR("DHT22 device not ready");
    return;
  }
  // Fetch sensor data
  int ret = sensor_sample_fetch(dht22_dev);
  if (ret != 0) {
    LOG_ERR("Failed to fetch sensor data: %d", ret);
    return;
  }
  struct sensor_value temp_val;
  ret = sensor_channel_get(dht22_dev, SENSOR_CHAN_AMBIENT_TEMP, &temp_val);
  if (ret != 0) {
    LOG_ERR("Failed to get temperature: %d", ret);
    return;
  }
  struct sensor_value hum_val;
  ret = sensor_channel_get(dht22_dev, SENSOR_CHAN_HUMIDITY, &hum_val);
  if (ret != 0) {
    LOG_ERR("Failed to get humidity: %d", ret);
    return;
  }
  // Convert to float
  practice_rpc_SensorTelemetry payload = practice_rpc_SensorTelemetry_init_zero;
  payload.temperature = sensor_value_to_float(&temp_val);
  payload.humidity = sensor_value_to_float(&hum_val);
  LOG_INF("DHT22: temp=%d deg C, humidity=%d percent", (int)payload.temperature,
          (int)payload.humidity);
  if (!sensor_pub_->publish(payload)) {
    LOG_WRN("Failed to publish sensor data");
  }
}

}  // namespace practice::rpc
