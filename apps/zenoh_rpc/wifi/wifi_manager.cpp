// Wi-Fi Manager Implementation

#include "wifi_manager.h"

#include <zephyr/logging/log.h>
#include <zephyr/net/net_event.h>
#include <zephyr/net/net_mgmt.h>
#include <zephyr/net/wifi_credentials.h>
#include <zephyr/net/wifi_mgmt.h>
#include <zephyr/settings/settings.h>

#include <cstring>

LOG_MODULE_REGISTER(wifi_manager, LOG_LEVEL_INF);

namespace wifi {

// Static callback structure
static struct net_mgmt_event_callback wifi_mgmt_cb;

// Global instance
static WifiManager g_wifi_manager;

WifiManager& get_wifi_manager() { return g_wifi_manager; }

// Callback context for wifi_credentials_for_each_ssid
struct SsidIterContext {
  char* ssid_buf;
  size_t ssid_buf_size;
  bool found;
};

// Static callback for SSID iteration
static void ssid_iter_callback(void* cb_arg, const char* ssid,
                               size_t ssid_len) {
  auto* ctx = static_cast<SsidIterContext*>(cb_arg);
  if (!ctx->found && ssid_len > 0 && ssid_len < ctx->ssid_buf_size) {
    memcpy(ctx->ssid_buf, ssid, ssid_len);
    ctx->ssid_buf[ssid_len] = '\0';
    ctx->found = true;
  }
}

bool WifiManager::init() {
  if (initialized_) {
    return true;
  }

  LOG_INF("Initializing Wi-Fi manager...");

  // Initialize settings subsystem (required for wifi_credentials)
  int ret = settings_subsys_init();
  if (ret != 0) {
    LOG_ERR("Failed to initialize settings subsystem: %d", ret);
    return false;
  }

  // Get default network interface (should be Wi-Fi)
  iface_ = net_if_get_default();
  if (!iface_) {
    LOG_ERR("No default network interface found");
    return false;
  }

  // Register event callbacks
  register_event_callbacks();

  initialized_ = true;
  LOG_INF("Wi-Fi manager initialized");
  return true;
}

void WifiManager::register_event_callbacks() {
  net_mgmt_init_event_callback(&wifi_mgmt_cb, wifi_event_handler,
                               NET_EVENT_WIFI_CONNECT_RESULT |
                                   NET_EVENT_WIFI_DISCONNECT_RESULT |
                                   NET_EVENT_IPV4_ADDR_ADD);
  net_mgmt_add_event_callback(&wifi_mgmt_cb);
}

void WifiManager::wifi_event_handler(struct net_mgmt_event_callback* cb,
                                     uint64_t mgmt_event,
                                     struct net_if* iface) {
  WifiManager& mgr = get_wifi_manager();

  if (mgmt_event == NET_EVENT_WIFI_CONNECT_RESULT) {
    const struct wifi_status* status = (const struct wifi_status*)cb->info;
    if (status->status == 0) {
      LOG_INF("Wi-Fi connected successfully");
      mgr.connected_ = true;
    } else {
      LOG_ERR("Wi-Fi connection failed: %d", status->status);
      mgr.connected_ = false;
    }
  } else if (mgmt_event == NET_EVENT_WIFI_DISCONNECT_RESULT) {
    LOG_WRN("Wi-Fi disconnected");
    mgr.connected_ = false;
  } else if (mgmt_event == NET_EVENT_IPV4_ADDR_ADD) {
    char addr_str[NET_IPV4_ADDR_LEN];
    struct net_if_addr* if_addr = (struct net_if_addr*)cb->info;
    if (if_addr && if_addr->address.family == AF_INET) {
      net_addr_ntop(AF_INET, &if_addr->address.in_addr, addr_str,
                    sizeof(addr_str));
      LOG_INF("Got IPv4 address: %s", addr_str);
    }
  }
}

bool WifiManager::has_stored_credentials() {
  if (!initialized_) {
    LOG_ERR("Wi-Fi manager not initialized");
    return false;
  }

  return !wifi_credentials_is_empty();
}

bool WifiManager::connect_from_storage() {
  if (!initialized_) {
    LOG_ERR("Wi-Fi manager not initialized");
    return false;
  }

  if (wifi_credentials_is_empty()) {
    LOG_INF("No stored Wi-Fi credentials");
    return false;
  }

  LOG_INF("Connecting using stored credentials...");

  // Get first stored SSID using iteration callback
  char ssid[WIFI_SSID_MAX_LEN + 1] = {0};
  SsidIterContext ctx = {ssid, sizeof(ssid), false};

  wifi_credentials_for_each_ssid(ssid_iter_callback, &ctx);

  if (!ctx.found || strlen(ssid) == 0) {
    LOG_WRN("No valid SSID found in stored credentials");
    return false;
  }

  LOG_INF("Found stored SSID: %s", ssid);

  // Get full credentials for this SSID
  char password[WIFI_PSK_MAX_LEN + 1] = {0};
  size_t password_len = 0;
  enum wifi_security_type security;
  uint8_t bssid[6];
  uint32_t flags;
  uint8_t channel;
  uint32_t timeout;

  int ret = wifi_credentials_get_by_ssid_personal(
      ssid, strlen(ssid), &security, bssid, sizeof(bssid), password,
      sizeof(password), &password_len, &flags, &channel, &timeout);
  if (ret != 0) {
    LOG_ERR("Failed to retrieve credentials for SSID %s: %d", ssid, ret);
    return false;
  }

  password[password_len] = '\0';
  return connect(ssid, password);
}

bool WifiManager::configure_and_connect(const char* ssid,
                                        const char* password) {
  if (!initialized_) {
    LOG_ERR("Wi-Fi manager not initialized");
    return false;
  }

  if (!ssid || strlen(ssid) == 0) {
    LOG_ERR("Invalid SSID");
    return false;
  }

  LOG_INF("Saving Wi-Fi credentials for SSID: %s", ssid);
  wifi_credentials_delete_all();
  // Delete any existing credentials for this SSID first
  wifi_credentials_delete_by_ssid(ssid, strlen(ssid));

  // Save new credentials (WPA2-PSK)
  int ret = wifi_credentials_set_personal(ssid, strlen(ssid),
                                          WIFI_SECURITY_TYPE_PSK,  // WPA2-PSK
                                          NULL, 0,  // BSSID (NULL = any)
                                          password, strlen(password),
                                          0,  // flags
                                          0,  // channel (0 = auto)
                                          0   // timeout
  );

  if (ret != 0) {
    LOG_ERR("Failed to save Wi-Fi credentials: %d", ret);
    return false;
  }

  LOG_INF("Wi-Fi credentials saved to NVS");

  // Connect immediately
  return connect(ssid, password);
}
bool WifiManager::connect(const char* ssid, const char* password) {
  if (!iface_) {
    LOG_ERR("No network interface");
    return false;
  }

  LOG_INF("Connecting to Wi-Fi: %s", ssid);

  LOG_INF("Scanning before connect...");
  net_mgmt(NET_REQUEST_WIFI_SCAN, iface_, NULL, 0);
  k_sleep(K_SECONDS(5));

  // Save current SSID
  strncpy(current_ssid_, ssid, sizeof(current_ssid_) - 1);
  current_ssid_[sizeof(current_ssid_) - 1] = '\0';

  // Prepare connection parameters
  for (int i = 0; i < 6; i++) {
    struct wifi_connect_req_params params = {};
    params.ssid = (const uint8_t*)ssid;
    params.ssid_length = strlen(ssid);
    params.psk = (const uint8_t*)password;
    params.psk_length = strlen(password);
    params.security = WIFI_SECURITY_TYPE_PSK;  // WPA2
    params.channel = WIFI_CHANNEL_ANY;
    params.timeout = SYS_FOREVER_MS;
    params.mfp = WIFI_MFP_OPTIONAL;

    int ret =
        net_mgmt(NET_REQUEST_WIFI_CONNECT, iface_, &params, sizeof(params));
    if (ret != 0) {
      LOG_ERR("Wi-Fi connect request failed: %d", ret);
      if (i == 5) {
        connected_ = false;
        return false;
      } else {
        k_sleep(K_SECONDS(1));
        continue;
      }
    }
  }

  LOG_INF("Wi-Fi connection request ok");
  connected_ = true;
  return true;
}

}  // namespace wifi
