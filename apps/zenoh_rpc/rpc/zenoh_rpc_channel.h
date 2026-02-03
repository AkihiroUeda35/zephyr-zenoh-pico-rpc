// Zenoh RPC Channel - Transport abstraction for RPC over Zenoh
// Supports USB-CDC ACM serial transport

#pragma once

#include <pb_encode.h>
#include <zenoh-pico.h>

#include <cstdint>
#include <functional>

namespace zenoh_rpc {

// RPC call result
enum class RpcStatus {
  OK,
  TIMEOUT,
  ENCODE_ERROR,
  DECODE_ERROR,
  TRANSPORT_ERROR,
  NOT_FOUND,
};

// Request/Response buffer
struct RpcBuffer {
  const uint8_t* data;
  size_t size;
};

// Maximum number of queryables that can be registered
constexpr size_t kMaxQueryables = 16;

// Buffer sizes
constexpr size_t kMaxKeyExprLen = 128;

// Zenoh RPC Channel (common transport for client and server)
class ZenohRpcChannel {
 public:
  explicit ZenohRpcChannel(z_loaned_session_t* session,
                           const char* device_id = nullptr);
  ~ZenohRpcChannel();

  // Non-copyable
  ZenohRpcChannel(const ZenohRpcChannel&) = delete;
  ZenohRpcChannel& operator=(const ZenohRpcChannel&) = delete;

  // Client side: synchronous RPC call
  RpcStatus call(const char* service_name, const char* method_name,
                 const RpcBuffer& request, uint8_t* response_buf,
                 size_t response_buf_size, size_t* response_size,
                 uint32_t timeout_ms = 5000);

  using RequestHandler = std::function<RpcStatus(
      pb_istream_t* req_stream, pb_ostream_t* response_stream)>;

  // Server side: register handler for a specific method
  bool register_handler(const char* service_name, const char* method_name,
                        RequestHandler handler);

  // Get the session
  z_loaned_session_t* session() const { return session_; }

 private:
  z_loaned_session_t* session_;
  const char* device_id_;

  // Registered queryables
  struct QueryableEntry {
    z_owned_queryable_t queryable;
    RequestHandler handler;
    bool active;
    char key_expr[kMaxKeyExprLen];
  };
  QueryableEntry queryables_[kMaxQueryables];
  size_t queryable_count_;

  // Build key expression for RPC
  void build_key_expr(char* buf, size_t buf_size, const char* service_name,
                      const char* method_name);

  // Query callback dispatcher
  static void query_callback(z_loaned_query_t* query, void* context);

  // NanoPB write callback context
  struct NanoPbZenohWriterContext {
    z_loaned_bytes_writer_t* writer;
    bool error;
  };
  static bool nanopb_zenoh_read_callback(pb_istream_t* stream, uint8_t* buf,
                                         size_t count);
  // NanoPB callback for writing to Zenoh bytes writer
  static bool nanopb_zenoh_write_callback(pb_ostream_t* stream,
                                          const uint8_t* buf, size_t count);
};

}  // namespace zenoh_rpc
