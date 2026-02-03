// Wi-Fi Manager for Raspberry Pi Pico 2 W
// Handles Wi-Fi connection, credential storage (NVS), and auto-connect on boot

#pragma once

#include <zephyr/kernel.h>
#include <zephyr/net/net_if.h>

namespace wifi {

/**
 * @brief Wi-Fi Manager class
 *
 * Provides functionality to:
 * - Save/load Wi-Fi credentials from NVS (via wifi_credentials library)
 * - Connect to Wi-Fi network
 * - Auto-connect on boot if credentials are stored
 */
class WifiManager {
 public:
  WifiManager() = default;
  ~WifiManager() = default;

  // Non-copyable
  WifiManager(const WifiManager&) = delete;
  WifiManager& operator=(const WifiManager&) = delete;

  /**
   * @brief Initialize the Wi-Fi manager
   *
   * Sets up event callbacks and prepares for connection.
   * Must be called before any other methods.
   *
   * @return true if initialization successful
   */
  bool init();

  /**
   * @brief Check if credentials are stored in NVS
   *
   * @return true if valid credentials exist
   */
  bool has_stored_credentials();

  /**
   * @brief Connect using stored credentials
   *
   * Loads SSID/password from NVS and initiates connection.
   *
   * @return true if connection initiated (not necessarily successful)
   */
  bool connect_from_storage();

  /**
   * @brief Save credentials to NVS and connect
   *
   * @param ssid SSID (max 32 chars)
   * @param password Password (max 64 chars)
   * @return true if credentials saved and connection initiated
   */
  bool configure_and_connect(const char* ssid, const char* password);

  /**
   * @brief Check if currently connected to Wi-Fi
   *
   * @return true if connected
   */
  bool is_connected() const { return connected_; }

  /**
   * @brief Get current SSID (if connected)
   *
   * @return SSID string or empty string if not connected
   */
  const char* get_ssid() const { return current_ssid_; }

 private:
  /**
   * @brief Internal connect method
   *
   * @param ssid SSID to connect to
   * @param password Password
   * @return true if connection request sent successfully
   */
  bool connect(const char* ssid, const char* password);

  /**
   * @brief Register net_mgmt event callbacks
   */
  void register_event_callbacks();

  /**
   * @brief Static event handler for Wi-Fi events
   */
  static void wifi_event_handler(struct net_mgmt_event_callback* cb,
                                 uint64_t mgmt_event, struct net_if* iface);

  // State
  bool initialized_ = false;
  bool connected_ = false;
  char current_ssid_[33] = {0};  // Max 32 chars + null terminator

  // Network interface
  struct net_if* iface_ = nullptr;
};

// Global instance (singleton pattern for Zephyr callback compatibility)
WifiManager& get_wifi_manager();

}  // namespace wifi
