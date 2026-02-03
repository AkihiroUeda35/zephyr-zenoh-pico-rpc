#include "service_server.h"
#include <pb_encode.h>
#include <pb_decode.h>
#include <pb_common.h>
#include "log_wrapper.h"

#ifdef __ZEPHYR__
LOG_MODULE_REGISTER(service_server, LOG_LEVEL_INF);
#endif  // __ZEPHYR__

namespace practice::rpc {

DeviceServiceServer::DeviceServiceServer(zenoh_rpc::ZenohRpcChannel& channel, DeviceService& impl)
    : channel_(channel), impl_(impl) {}

bool DeviceServiceServer::register_handlers() {
  bool success = true;

  // SetLed
  success &= channel_.register_handler(
      kServiceName, "SetLed",
      [this](pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
        return handle_SetLed(req_stream, resp_stream);
      });

  // Echo
  success &= channel_.register_handler(
      kServiceName, "Echo",
      [this](pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
        return handle_Echo(req_stream, resp_stream);
      });

  // EchoMalloc
  success &= channel_.register_handler(
      kServiceName, "EchoMalloc",
      [this](pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
        return handle_EchoMalloc(req_stream, resp_stream);
      });

  // StartSensorStream
  success &= channel_.register_handler(
      kServiceName, "StartSensorStream",
      [this](pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
        return handle_StartSensorStream(req_stream, resp_stream);
      });

  // StopSensorStream
  success &= channel_.register_handler(
      kServiceName, "StopSensorStream",
      [this](pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
        return handle_StopSensorStream(req_stream, resp_stream);
      });

  // ConfigureWifi
  success &= channel_.register_handler(
      kServiceName, "ConfigureWifi",
      [this](pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
        return handle_ConfigureWifi(req_stream, resp_stream);
      });

  if (success) {
    LOG_INF("All DeviceService handlers registered");
  } else {
    LOG_ERR("Failed to register some DeviceService handlers");
  }
  return success;
}

zenoh_rpc::RpcStatus DeviceServiceServer::handle_SetLed(
    pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
  // Decode request
  practice_rpc_LedRequest request = practice_rpc_LedRequest_init_zero;
  if (!pb_decode(req_stream, practice_rpc_LedRequest_fields, &request)) {
    LOG_ERR("Failed to decode LedRequest");
    return zenoh_rpc::RpcStatus::DECODE_ERROR;
  }

  // Call implementation
  practice_rpc_LedResponse response = practice_rpc_LedResponse_init_zero;
  zenoh_rpc::RpcStatus status = impl_.SetLed(request, &response);
  if (status != zenoh_rpc::RpcStatus::OK) {
    return status;
  }

  // Encode response directly to stream (zero-copy)
  if (!pb_encode(resp_stream, practice_rpc_LedResponse_fields, &response)) {
    LOG_ERR("Failed to encode LedResponse");
    return zenoh_rpc::RpcStatus::ENCODE_ERROR;
  }

  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceServer::handle_Echo(
    pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
  // Decode request
  practice_rpc_EchoRequest request = practice_rpc_EchoRequest_init_zero;
  if (!pb_decode(req_stream, practice_rpc_EchoRequest_fields, &request)) {
    LOG_ERR("Failed to decode EchoRequest");
    return zenoh_rpc::RpcStatus::DECODE_ERROR;
  }

  // Call implementation
  practice_rpc_EchoResponse response = practice_rpc_EchoResponse_init_zero;
  zenoh_rpc::RpcStatus status = impl_.Echo(request, &response);
  if (status != zenoh_rpc::RpcStatus::OK) {
    return status;
  }

  // Encode response directly to stream (zero-copy)
  if (!pb_encode(resp_stream, practice_rpc_EchoResponse_fields, &response)) {
    LOG_ERR("Failed to encode EchoResponse");
    return zenoh_rpc::RpcStatus::ENCODE_ERROR;
  }

  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceServer::handle_EchoMalloc(
    pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
  // Decode request
  practice_rpc_EchoRequestMalloc request = practice_rpc_EchoRequestMalloc_init_zero;
  if (!pb_decode(req_stream, practice_rpc_EchoRequestMalloc_fields, &request)) {
    LOG_ERR("Failed to decode EchoRequestMalloc");
    return zenoh_rpc::RpcStatus::DECODE_ERROR;
  }

  // Call implementation
  practice_rpc_EchoResponseMalloc response = practice_rpc_EchoResponseMalloc_init_zero;
  zenoh_rpc::RpcStatus status = impl_.EchoMalloc(request, &response);
  if (status != zenoh_rpc::RpcStatus::OK) {
    pb_release(practice_rpc_EchoRequestMalloc_fields, &request);
    return status;
  }

  // Encode response directly to stream (zero-copy)
  if (!pb_encode(resp_stream, practice_rpc_EchoResponseMalloc_fields, &response)) {
    LOG_ERR("Failed to encode EchoResponseMalloc");
    pb_release(practice_rpc_EchoRequestMalloc_fields, &request);
    pb_release(practice_rpc_EchoResponseMalloc_fields, &response);
    return zenoh_rpc::RpcStatus::ENCODE_ERROR;
  }

  // Release allocated memory
  pb_release(practice_rpc_EchoRequestMalloc_fields, &request);
  pb_release(practice_rpc_EchoResponseMalloc_fields, &response);

  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceServer::handle_StartSensorStream(
    pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
  // Decode request
  practice_rpc_SensorRequest request = practice_rpc_SensorRequest_init_zero;
  if (!pb_decode(req_stream, practice_rpc_SensorRequest_fields, &request)) {
    LOG_ERR("Failed to decode SensorRequest");
    return zenoh_rpc::RpcStatus::DECODE_ERROR;
  }

  // Call implementation
  practice_rpc_Empty response = practice_rpc_Empty_init_zero;
  zenoh_rpc::RpcStatus status = impl_.StartSensorStream(request, &response);
  if (status != zenoh_rpc::RpcStatus::OK) {
    return status;
  }

  // Encode response directly to stream (zero-copy)
  if (!pb_encode(resp_stream, practice_rpc_Empty_fields, &response)) {
    LOG_ERR("Failed to encode Empty");
    return zenoh_rpc::RpcStatus::ENCODE_ERROR;
  }

  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceServer::handle_StopSensorStream(
    pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
  // Decode request
  practice_rpc_Empty request = practice_rpc_Empty_init_zero;
  if (!pb_decode(req_stream, practice_rpc_Empty_fields, &request)) {
    LOG_ERR("Failed to decode Empty");
    return zenoh_rpc::RpcStatus::DECODE_ERROR;
  }

  // Call implementation
  practice_rpc_Empty response = practice_rpc_Empty_init_zero;
  zenoh_rpc::RpcStatus status = impl_.StopSensorStream(request, &response);
  if (status != zenoh_rpc::RpcStatus::OK) {
    return status;
  }

  // Encode response directly to stream (zero-copy)
  if (!pb_encode(resp_stream, practice_rpc_Empty_fields, &response)) {
    LOG_ERR("Failed to encode Empty");
    return zenoh_rpc::RpcStatus::ENCODE_ERROR;
  }

  return zenoh_rpc::RpcStatus::OK;
}

zenoh_rpc::RpcStatus DeviceServiceServer::handle_ConfigureWifi(
    pb_istream_t* req_stream, pb_ostream_t* resp_stream) {
  // Decode request
  practice_rpc_WifiSettings request = practice_rpc_WifiSettings_init_zero;
  if (!pb_decode(req_stream, practice_rpc_WifiSettings_fields, &request)) {
    LOG_ERR("Failed to decode WifiSettings");
    return zenoh_rpc::RpcStatus::DECODE_ERROR;
  }

  // Call implementation
  practice_rpc_Empty response = practice_rpc_Empty_init_zero;
  zenoh_rpc::RpcStatus status = impl_.ConfigureWifi(request, &response);
  if (status != zenoh_rpc::RpcStatus::OK) {
    return status;
  }

  // Encode response directly to stream (zero-copy)
  if (!pb_encode(resp_stream, practice_rpc_Empty_fields, &response)) {
    LOG_ERR("Failed to encode Empty");
    return zenoh_rpc::RpcStatus::ENCODE_ERROR;
  }

  return zenoh_rpc::RpcStatus::OK;
}

}  // namespace practice::rpc