// Zenoh Pub/Sub - Implementation

#include "zenoh_pubsub.h"

#include <cstdio>
#include <cstring>

#include "log_wrapper.h"

#ifdef __ZEPHYR__
LOG_MODULE_REGISTER(zenoh_pubsub, LOG_LEVEL_INF);
#endif  // __ZEPHYR__

namespace zenoh_rpc {

// ============================================================================
// LogPublisher
// ============================================================================

LogPublisher::LogPublisher(z_loaned_session_t* session, const char* device_id)
    : valid_(false) {
  char key_expr[kMaxTopicLen];
  snprintf(key_expr, sizeof(key_expr), "%s/log", device_id);

  z_view_keyexpr_t ke;
  if (z_view_keyexpr_from_str(&ke, key_expr) != Z_OK) {
    LOG_ERR("LogPublisher: Failed to create keyexpr: %s", key_expr);
    return;
  }

  z_publisher_options_t opts;
  z_publisher_options_default(&opts);
  opts.congestion_control = Z_CONGESTION_CONTROL_BLOCK;
  LOG_INF("LogPublisher: Declaring publisher for: %s", key_expr);
  z_result_t res = z_declare_publisher(session, &publisher_, z_loan(ke), &opts);
  if (res != Z_OK) {
    LOG_ERR("LogPublisher: z_declare_publisher failed: %d", res);
    return;
  }
  valid_ = true;
  LOG_INF("LogPublisher: Publisher created successfully");
}

LogPublisher::~LogPublisher() {
  if (valid_) {
    z_undeclare_publisher(z_publisher_move(&publisher_));
  }
}

const char* LogPublisher::level_string(LogLevel level) {
  switch (level) {
    case LogLevel::DEBUG:
      return "DEBUG";
    case LogLevel::INFO:
      return "INFO";
    case LogLevel::WARN:
      return "WARN";
    case LogLevel::ERROR:
      return "ERROR";
    default:
      return "UNKNOWN";
  }
}

void LogPublisher::log_impl(LogLevel level, const char* format, va_list args) {
  if (!valid_) {
    return;
  }
  char buffer_[kMaxLogMessageLen];
  int prefix_len =
      snprintf(buffer_, sizeof(buffer_), "[%s] ", level_string(level));
  if (prefix_len < 0) {
    return;
  }
  vsnprintf(buffer_ + prefix_len, sizeof(buffer_) - prefix_len, format, args);
  z_owned_bytes_t payload;
  z_bytes_copy_from_buf(&payload, reinterpret_cast<const uint8_t*>(buffer_),
                        strlen(buffer_));
  z_publisher_put(z_publisher_loan(&publisher_), z_bytes_move(&payload), NULL);
}

void LogPublisher::log(LogLevel level, const char* format, ...) {
  va_list args;
  va_start(args, format);
  log_impl(level, format, args);
  va_end(args);
}

void LogPublisher::log_debug(const char* format, ...) {
  va_list args;
  va_start(args, format);
  log_impl(LogLevel::DEBUG, format, args);
  va_end(args);
}

void LogPublisher::log_info(const char* format, ...) {
  va_list args;
  va_start(args, format);
  log_impl(LogLevel::INFO, format, args);
  va_end(args);
}

void LogPublisher::log_warn(const char* format, ...) {
  va_list args;
  va_start(args, format);
  log_impl(LogLevel::WARN, format, args);
  va_end(args);
}

void LogPublisher::log_error(const char* format, ...) {
  va_list args;
  va_start(args, format);
  log_impl(LogLevel::ERROR, format, args);
  va_end(args);
}

}  // namespace zenoh_rpc
