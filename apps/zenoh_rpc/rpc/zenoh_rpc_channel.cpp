// Zenoh RPC Channel - Implementation

#include "zenoh_rpc_channel.h"

#include <pb_decode.h>
#include <pb_encode.h>

#include <cstdio>
#include <cstring>

#include "log_wrapper.h"

#ifdef __ZEPHYR__
LOG_MODULE_REGISTER(zenoh_rpc_channel, LOG_LEVEL_INF);
#endif  // __ZEPHYR__

namespace zenoh_rpc {

ZenohRpcChannel::ZenohRpcChannel(z_loaned_session_t* session,
                                 const char* device_id)
    : session_(session), device_id_(device_id), queryable_count_(0) {
  for (size_t i = 0; i < kMaxQueryables; ++i) {
    queryables_[i].active = false;
    queryables_[i].key_expr[0] = '\0';
  }
}

ZenohRpcChannel::~ZenohRpcChannel() {
  // Undeclare all queryables
  for (size_t i = 0; i < kMaxQueryables; ++i) {
    if (queryables_[i].active) {
      z_undeclare_queryable(z_queryable_move(&queryables_[i].queryable));
      queryables_[i].active = false;
    }
  }
}

void ZenohRpcChannel::build_key_expr(char* buf, size_t buf_size,
                                     const char* service_name,
                                     const char* method_name) {
  if (device_id_ && strlen(device_id_) > 0) {
    snprintf(buf, buf_size, "%s/rpc/%s/%s", device_id_, service_name,
             method_name);
  } else {
    snprintf(buf, buf_size, "rpc/%s/%s", service_name, method_name);
  }
}

RpcStatus ZenohRpcChannel::call(const char* service_name,
                                const char* method_name,
                                const RpcBuffer& request, uint8_t* response_buf,
                                size_t response_buf_size, size_t* response_size,
                                uint32_t timeout_ms) {
#if Z_FEATURE_QUERY == 1
  char key_expr_str[kMaxKeyExprLen];
  build_key_expr(key_expr_str, sizeof(key_expr_str), service_name, method_name);

  z_view_keyexpr_t keyexpr;
  if (z_view_keyexpr_from_str(&keyexpr, key_expr_str) != Z_OK) {
    LOG_ERR("Failed to create keyexpr: %s", key_expr_str);
    return RpcStatus::TRANSPORT_ERROR;
  }

  // Create payload from request
  z_owned_bytes_t payload;
  z_bytes_copy_from_buf(&payload, request.data, request.size);

  // Configure get options
  z_get_options_t opts;
  z_get_options_default(&opts);
  opts.payload = z_bytes_move(&payload);
  opts.timeout_ms = timeout_ms;

  // Create reply channel
  z_owned_fifo_handler_reply_t handler;
  z_owned_closure_reply_t closure;
  z_fifo_channel_reply_new(&closure, &handler, 1);

  // Execute query
  z_result_t res = z_get(session_, z_view_keyexpr_loan(&keyexpr), "",
                         z_closure_reply_move(&closure), &opts);
  if (res != Z_OK) {
    LOG_ERR("z_get failed: %d", res);
    z_fifo_handler_reply_drop(z_fifo_handler_reply_move(&handler));
    return RpcStatus::TRANSPORT_ERROR;
  }

  // Wait for reply
  z_owned_reply_t reply;
  z_result_t recv_res =
      z_fifo_handler_reply_recv(z_fifo_handler_reply_loan(&handler), &reply);
  z_fifo_handler_reply_drop(z_fifo_handler_reply_move(&handler));

  if (recv_res != Z_OK) {
    LOG_WRN("No reply received (timeout or error)");
    return RpcStatus::TIMEOUT;
  }

  // Check if reply is ok
  if (!z_reply_is_ok(z_reply_loan(&reply))) {
    LOG_ERR("Reply error");
    z_reply_drop(z_reply_move(&reply));
    return RpcStatus::TRANSPORT_ERROR;
  }

  // Extract payload from reply
  const z_loaned_sample_t* sample = z_reply_ok(z_reply_loan(&reply));
  z_bytes_reader_t reader = z_bytes_get_reader(z_sample_payload(sample));

  size_t payload_len = z_bytes_len(z_sample_payload(sample));
  if (payload_len > response_buf_size) {
    LOG_ERR("Response buffer too small: need %zu, have %zu", payload_len,
            response_buf_size);
    z_reply_drop(z_reply_move(&reply));
    return RpcStatus::DECODE_ERROR;
  }

  z_bytes_reader_read(&reader, response_buf, payload_len);
  *response_size = payload_len;

  z_reply_drop(z_reply_move(&reply));
  return RpcStatus::OK;
#else
  LOG_ERR("Query feature not enabled");
  return RpcStatus::TRANSPORT_ERROR;
#endif
}

bool ZenohRpcChannel::nanopb_zenoh_write_callback(pb_ostream_t* stream,
                                                  const uint8_t* buf,
                                                  size_t count) {
  auto* ctx = static_cast<NanoPbZenohWriterContext*>(stream->state);
  if (ctx->error) {
    return false;
  }

  z_result_t res = z_bytes_writer_write_all(ctx->writer, buf, count);
  if (res != Z_OK) {
    LOG_ERR("z_bytes_writer_write_all failed: %d", res);
    ctx->error = true;
    return false;
  }

  return true;
}

void ZenohRpcChannel::query_callback(z_loaned_query_t* query, void* context) {
  auto* entry = static_cast<QueryableEntry*>(context);
  if (!entry || !entry->active || !entry->handler) {
    LOG_ERR("Invalid queryable entry in callback");
    return;
  }

  const z_loaned_bytes_t* payload = z_query_payload(query);
  z_bytes_reader_t reader = z_bytes_get_reader(payload);
  size_t payload_len = z_bytes_len(payload);

  pb_istream_t istream = {.callback = nanopb_zenoh_read_callback,
                          .state = &reader,
                          .bytes_left = payload_len,
                          .errmsg = NULL};

  z_owned_bytes_writer_t writer;
  if (z_bytes_writer_empty(&writer) != Z_OK) {
    LOG_ERR("Failed to create bytes writer");
    return;
  }
  z_loaned_bytes_writer_t* writer_loan = z_bytes_writer_loan_mut(&writer);

  NanoPbZenohWriterContext write_ctx = {writer_loan, false};
  pb_ostream_t ostream = {.callback = nanopb_zenoh_write_callback,
                          .state = &write_ctx,
                          .max_size = SIZE_MAX,
                          .bytes_written = 0,
                          .errmsg = NULL};

  RpcStatus status = entry->handler(&istream, &ostream);

  if (status != RpcStatus::OK || write_ctx.error) {
    LOG_ERR("Handler returned error: %d or write error",
            static_cast<int>(status));
    z_drop(z_bytes_writer_move(&writer));
    return;
  }

  z_owned_bytes_t reply_payload;
  z_bytes_writer_finish(z_bytes_writer_move(&writer), &reply_payload);

  z_query_reply_options_t reply_opts;
  z_query_reply_options_default(&reply_opts);

  const z_loaned_keyexpr_t* query_keyexpr = z_query_keyexpr(query);
  z_result_t res = z_query_reply(query, query_keyexpr,
                                 z_bytes_move(&reply_payload), &reply_opts);
  if (res != Z_OK) {
    LOG_ERR("z_query_reply failed: %d", res);
  }
}
bool ZenohRpcChannel::register_handler(const char* service_name,
                                       const char* method_name,
                                       RequestHandler handler) {
#if Z_FEATURE_QUERYABLE == 1
  if (queryable_count_ >= kMaxQueryables) {
    LOG_ERR("Max queryables reached");
    return false;
  }

  // Find free slot
  size_t slot = 0;
  for (; slot < kMaxQueryables; ++slot) {
    if (!queryables_[slot].active) {
      break;
    }
  }
  if (slot >= kMaxQueryables) {
    LOG_ERR("No free queryable slot");
    return false;
  }

  QueryableEntry& entry = queryables_[slot];
  build_key_expr(entry.key_expr, sizeof(entry.key_expr), service_name,
                 method_name);
  entry.handler = std::move(handler);

  z_view_keyexpr_t keyexpr;
  if (z_view_keyexpr_from_str(&keyexpr, entry.key_expr) != Z_OK) {
    LOG_ERR("Failed to create keyexpr: %s", entry.key_expr);
    return false;
  }

  // Create callback closure
  z_owned_closure_query_t callback;
  z_closure_query(&callback, query_callback, nullptr, &entry);

  z_queryable_options_t opts;
  z_queryable_options_default(&opts);

  z_result_t res = z_declare_queryable(session_, &entry.queryable,
                                       z_view_keyexpr_loan(&keyexpr),
                                       z_closure_query_move(&callback), &opts);
  if (res != Z_OK) {
    LOG_ERR("z_declare_queryable failed: %d for %s", res, entry.key_expr);
    return false;
  }

  entry.active = true;
  queryable_count_++;
  LOG_INF("Registered handler for: %s", entry.key_expr);
  return true;
#else
  LOG_ERR("Queryable feature not enabled");
  return false;
#endif
}
bool ZenohRpcChannel::nanopb_zenoh_read_callback(pb_istream_t* stream,
                                                 uint8_t* buf, size_t count) {
  z_bytes_reader_t* reader = static_cast<z_bytes_reader_t*>(stream->state);
  z_bytes_reader_read(reader, buf, count);

  return true;
}
}  // namespace zenoh_rpc
