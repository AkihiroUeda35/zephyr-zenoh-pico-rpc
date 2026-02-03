#include <zenoh-pico.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/net/net_core.h>
#include <zephyr/net/net_if.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/usb/usb_device.h>

#include "rpc/service_server.h"
#include "rpc/zenoh_pubsub.h"
#include "rpc/zenoh_rpc_channel.h"
#include "service.pb.h"
#include "service_impl.h"
#include "wifi/wifi_manager.h"

LOG_MODULE_REGISTER(main, LOG_LEVEL_INF);

// Device ID for telemetry topics
#define DEVICE_ID "pico2w-001"

// LED GPIO (same as in device_service_impl.cpp)
#define LED0_NODE DT_ALIAS(led0)
static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(LED0_NODE, gpios);

// USB CDC-ACM device name
const struct device* usb_dev = DEVICE_DT_GET(DT_NODELABEL(cdc_acm_uart0));

// Wi-Fi Zenoh router address
#define WIFI_ZENOH_ROUTER_ADDR "192.168.0.2"

// Zenoh server port
#define ZENOH_LISTEN_PORT "7447"

// Check if DTR is set (Data Terminal Ready)
// This indicates that the host has opened the serial port
static bool is_dtr_set(const struct device* dev) {
  uint32_t dtr = 0;
  int ret = uart_line_ctrl_get(dev, UART_LINE_CTRL_DTR, &dtr);
  if (ret < 0) {
    LOG_WRN("Failed to get DTR status: %d", ret);
    return false;
  }
  return (dtr != 0);
}

extern "C" {
int main() {
  LOG_INF("Zenoh RPC Server Starting...");
  // Initialize LED GPIO
  if (!gpio_is_ready_dt(&led)) {
    printk("LED: device not ready.\n");
  }
  if (gpio_pin_configure_dt(&led, GPIO_OUTPUT_LOW) < 0) {
    printk("LED: device not configured.\n");
  }

  // Initialize USB
  LOG_INF("Initializing USB...");
  int ret = usb_enable(NULL);
  if (ret != 0) {
    LOG_ERR("Failed to enable USB: %d", ret);
    return 0;
  }
  if (!device_is_ready(usb_dev)) {
    LOG_ERR("CDC-ACM device not ready");
    return 0;
  }
  LOG_INF("CDC-ACM device ready: %s", usb_dev->name);

  // Initialize Wi-Fi manager
  wifi::WifiManager& wifi_mgr = wifi::get_wifi_manager();
  if (wifi_mgr.init()) {
    // Check for stored credentials and auto-connect
    if (wifi_mgr.has_stored_credentials()) {
      LOG_INF("Found stored Wi-Fi credentials, connecting...");
      if (wifi_mgr.connect_from_storage()) {
        LOG_INF("Wi-Fi connection initiated");
        // Give some time for Wi-Fi to connect
        k_sleep(K_SECONDS(5));
      } else {
        LOG_WRN("Failed to initiate Wi-Fi connection");
      }
    } else {
      LOG_INF("No stored Wi-Fi credentials");
    }
  } else {
    LOG_ERR("Failed to initialize Wi-Fi manager");
  }
  // Zenoh connection Loop
  bool use_wifi = wifi_mgr.is_connected();
  LOG_INF("Establishing Zenoh session (use_wifi=%d)...", use_wifi);
  z_owned_session_t session;
  while (true) {
    // Initialize Zenoh configuration
    z_owned_config_t config;
    z_config_default(&config);
    zp_config_insert(z_config_loan_mut(&config), Z_CONFIG_MODE_KEY, "client");
    // Configure transport based on Wi-Fi or USB-ACM connection status
    if (use_wifi) {
      LOG_INF("Wi-Fi connected, using TCP connection...");
      zp_config_insert(z_config_loan_mut(&config), Z_CONFIG_CONNECT_KEY,
                       "tcp/" WIFI_ZENOH_ROUTER_ADDR ":" ZENOH_LISTEN_PORT);
      LOG_INF("Connecting to tcp/" WIFI_ZENOH_ROUTER_ADDR
              ":" ZENOH_LISTEN_PORT);
    } else {
      LOG_INF("No Wi-Fi, using USB CDC-ACM serial...");
      // Check DTR before connecting
      if (is_dtr_set(usb_dev) == false) {
        LOG_WRN("DTR not set - waiting for host connection...");
        k_sleep(K_MSEC(1000));
        continue;
      }
      // Use serial link over USB CDC-ACM
      char connect_str[128];
      snprintf(connect_str, sizeof(connect_str), "serial/%s#baudrate=115200",
               usb_dev->name);
      zp_config_insert(z_config_loan_mut(&config), Z_CONFIG_CONNECT_KEY,
                       connect_str);
      LOG_INF("Connecting via %s", connect_str);
    }
    z_owned_session_t session_;
    LOG_INF("Opening Zenoh session...");
    z_result_t res = z_open(&session_, z_config_move(&config), NULL);
    if (res != Z_OK) {
      gpio_pin_toggle_dt(&led);
      LOG_ERR("z_open failed: %d, retrying...", res);
      k_sleep(K_MSEC(1000));
      continue;
    }
    session = session_;
    break;
  }
  gpio_pin_set_dt(&led, 0);
  LOG_INF("Zenoh session opened successfully");

  // Get loaned session (mutable loan for Pub/Sub and RPC)
  z_loaned_session_t* session_loan = z_session_loan_mut(&session);
  zenoh_rpc::ZenohRpcChannel channel(session_loan, DEVICE_ID);
  zenoh_rpc::TelemetryPublisher<practice_rpc_SensorTelemetry> sensor_pub(
      session_loan, DEVICE_ID, PRACTICE_RPC_SENSOR_TELEMETRY_ZENOH_KEY,
      practice_rpc_SensorTelemetry_fields);
  zenoh_rpc::LogPublisher log_pub(session_loan, DEVICE_ID);
  practice::rpc::DeviceServiceImpl service_impl(&sensor_pub, &log_pub);
  practice::rpc::DeviceServiceServer server(channel, service_impl);
  if (!server.register_handlers()) {
    LOG_ERR("Failed to register RPC handlers");
    z_drop(z_session_move(&session));
    return -1;
  }
  LOG_INF("Starting Zenoh read and lease tasks...");
  z_result_t read_res = zp_start_read_task(session_loan, NULL);
  z_result_t lease_res = zp_start_lease_task(session_loan, NULL);
  LOG_INF("Read task result: %d, Lease task result: %d", read_res, lease_res);
  if (read_res != Z_OK || lease_res != Z_OK) {
    LOG_ERR("Failed to start Zenoh tasks");
  }
  // Main loop: Sensor Publish
  LOG_INF("Entering main loop...");
  uint32_t loop_count = 0;
  while (true) {
    loop_count++;
    if (service_impl.is_streaming_enabled()) {
      LOG_INF("Loop %u: Publishing sensor data...", loop_count);
      service_impl.publish_sensor_data();
    } else {
      if (loop_count % 10 == 0) {
        LOG_INF("Loop %u: Streaming disabled", loop_count);
      }
    }
    k_sleep(K_MSEC(1000));
    if (use_wifi == false && is_dtr_set(usb_dev) == false) {
      LOG_WRN("DTR cleared - host disconnected");
      break;
    }
    if (zp_lease_task_is_running(session_loan) == false ||
        zp_read_task_is_running(session_loan) == false) {
      LOG_WRN("Keep-alive failed");
      break;
    }
  }
  // Reboot
  LOG_WRN("Rebooting system...");
  k_sleep(K_MSEC(1000));
  sys_reboot(SYS_REBOOT_COLD);
  // unreachable
  return 0;
}
}
