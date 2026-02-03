// Zenoh Pub/Sub - Publisher and Subscriber abstractions for telemetry and logs

#pragma once

#include <pb_encode.h>
#include <zenoh-pico.h>

#include <cstdarg>
#include <cstdint>
#include <functional>

#include "log_wrapper.h"

#define ZENOH_PUBLISH_PROTO_ZERO_COPY

namespace zenoh_rpc {

// Buffer sizes
constexpr size_t kMaxTopicLen = 128;
constexpr size_t kMaxLogMessageLen = 256;
constexpr size_t kMaxTelemetryPayloadSize = 256;

// Telemetry Publisher (typed wrapper with nanopb encoding)
template <typename T>
class TelemetryPublisher {
 public:
  TelemetryPublisher(z_loaned_session_t* session, const char* device_id,
                     const char* topic_suffix, const pb_msgdesc_t* fields)
      : fields_(fields), valid_(false) {
    char key_expr[kMaxTopicLen];
    snprintf(key_expr, sizeof(key_expr), "%s%s", device_id, topic_suffix);

    z_view_keyexpr_t ke;
    if (z_view_keyexpr_from_str(&ke, key_expr) != Z_OK) {
      __print("TelemetryPublisher: Failed to create keyexpr: %s\n", key_expr);
      return;
    }

    z_publisher_options_t opts;
    z_publisher_options_default(&opts);

    __print("TelemetryPublisher: Declaring publisher for: %s\n", key_expr);
    z_result_t res =
        z_declare_publisher(session, &publisher_, z_loan(ke), &opts);
    if (res != Z_OK) {
      __print("TelemetryPublisher: z_declare_publisher failed: %d\n", res);
      return;
    }

    valid_ = true;
    __print("TelemetryPublisher: Publisher created successfully\n");
  }

  ~TelemetryPublisher() {
    if (valid_) {
      z_undeclare_publisher(z_publisher_move(&publisher_));
    }
  }

  // Non-copyable, non-movable
  TelemetryPublisher(const TelemetryPublisher&) = delete;
  TelemetryPublisher& operator=(const TelemetryPublisher&) = delete;
  TelemetryPublisher(TelemetryPublisher&&) = delete;
  TelemetryPublisher& operator=(TelemetryPublisher&&) = delete;

  bool is_valid() const { return valid_; }

  bool publish(const T& message) {
    if (!valid_) {
      __print("TelemetryPublisher: publisher not valid\n");
      return false;
    }

    // Simple approach: encode to buffer first, then copy to Zenoh bytes
#ifndef ZENOH_PUBLISH_PROTO_ZERO_COPY
    uint8_t buffer[kMaxTelemetryPayloadSize];
    pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));

    if (!pb_encode(&stream, fields_, &message)) {
      __print("TelemetryPublisher: pb_encode failed\n");
      return false;
    }

    size_t message_size = stream.bytes_written;

    // Copy to Zenoh bytes
    z_owned_bytes_t bytes;
    z_bytes_copy_from_buf(&bytes, buffer, message_size);

    // Publish
    z_result_t res = z_publisher_put(z_publisher_loan(&publisher_),
                                     z_bytes_move(&bytes), NULL);

    if (res != Z_OK) {
      __print("TelemetryPublisher: z_publisher_put failed: %d\n", res);
      return false;
    }
    return true;
#else
    // Create Zenoh bytes writer for zero-copy encoding
    z_owned_bytes_writer_t writer;
    if (z_bytes_writer_empty(&writer) != Z_OK) {
      __print("TelemetryPublisher: bytes_writer_empty failed\n");
      return false;
    }
    z_loaned_bytes_writer_t* writer_loan = z_bytes_writer_loan_mut(&writer);

    // NanoPB context for Zenoh writer
    struct WriterContext {
      z_loaned_bytes_writer_t* writer;
      bool error;
    } ctx = {writer_loan, false};

    // Create NanoPB output stream with callback
    pb_ostream_t stream = {
        .callback = [](pb_ostream_t* s, const uint8_t* buf,
                       size_t count) -> bool {
          auto* c = static_cast<WriterContext*>(s->state);
          if (c->error) return false;
          if (z_bytes_writer_write_all(c->writer, buf, count) != Z_OK) {
            c->error = true;
            return false;
          }
          return true;
        },
        .state = &ctx,
        .max_size = SIZE_MAX,
        .bytes_written = 0,
        .errmsg = NULL};

    // Encode with NanoPB (writes directly to Zenoh writer)
    if (!pb_encode(&stream, fields_, &message) || ctx.error) {
      __print("TelemetryPublisher: pb_encode failed\n");
      z_drop(z_bytes_writer_move(&writer));
      return false;
    }

    // Finish and get bytes (zero-copy)
    z_owned_bytes_t bytes;
    z_bytes_writer_finish(z_bytes_writer_move(&writer), &bytes);

    // Publish
    z_result_t res = z_publisher_put(z_publisher_loan(&publisher_),
                                     z_bytes_move(&bytes), NULL);

    if (res != Z_OK) {
      __print("TelemetryPublisher: z_publisher_put failed: %d\n", res);
      return false;
    }
    __print("TelemetryPublisher: published successfully\n");
    return true;
#endif
  }

 private:
  const pb_msgdesc_t* fields_;
  z_owned_publisher_t publisher_;
  bool valid_;
};

// Log level
enum class LogLevel {
  DEBUG,
  INFO,
  WARN,
  ERROR,
};

// Log Publisher
class LogPublisher {
 public:
  LogPublisher(z_loaned_session_t* session, const char* device_id);
  ~LogPublisher();

  // Non-copyable
  LogPublisher(const LogPublisher&) = delete;
  LogPublisher& operator=(const LogPublisher&) = delete;

  bool is_valid() const { return valid_; }

  void log(LogLevel level, const char* format, ...);
  void log_debug(const char* format, ...);
  void log_info(const char* format, ...);
  void log_warn(const char* format, ...);
  void log_error(const char* format, ...);

 private:
  z_owned_publisher_t publisher_;
  bool valid_;

  void log_impl(LogLevel level, const char* format, va_list args);
  static const char* level_string(LogLevel level);
};

}  // namespace zenoh_rpc
