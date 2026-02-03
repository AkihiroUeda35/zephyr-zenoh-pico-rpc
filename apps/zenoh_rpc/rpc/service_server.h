#ifndef SERVICE_SERVER_H
#define SERVICE_SERVER_H

#include "zenoh_rpc_channel.h"
#include "service.pb.h"

#define PRACTICE_RPC_SENSOR_TELEMETRY_ZENOH_KEY "/telemetry/sensor"

namespace practice::rpc {

// Interface for DeviceService
class DeviceService {
 public:
  virtual ~DeviceService() = default;
  virtual zenoh_rpc::RpcStatus SetLed(const practice_rpc_LedRequest& req, practice_rpc_LedResponse* resp) = 0;
  virtual zenoh_rpc::RpcStatus Echo(const practice_rpc_EchoRequest& req, practice_rpc_EchoResponse* resp) = 0;
  virtual zenoh_rpc::RpcStatus EchoMalloc(const practice_rpc_EchoRequestMalloc& req, practice_rpc_EchoResponseMalloc* resp) = 0;
  virtual zenoh_rpc::RpcStatus StartSensorStream(const practice_rpc_SensorRequest& req, practice_rpc_Empty* resp) = 0;
  virtual zenoh_rpc::RpcStatus StopSensorStream(const practice_rpc_Empty& req, practice_rpc_Empty* resp) = 0;
  virtual zenoh_rpc::RpcStatus ConfigureWifi(const practice_rpc_WifiSettings& req, practice_rpc_Empty* resp) = 0;
};

class DeviceServiceServer {
 public:
  DeviceServiceServer(zenoh_rpc::ZenohRpcChannel& channel, DeviceService& impl);
  bool register_handlers();

 private:
  zenoh_rpc::ZenohRpcChannel& channel_;
  DeviceService& impl_;
  static constexpr const char* kServiceName = "DeviceService";

  zenoh_rpc::RpcStatus handle_SetLed(pb_istream_t* req_stream, pb_ostream_t* resp_stream);
  zenoh_rpc::RpcStatus handle_Echo(pb_istream_t* req_stream, pb_ostream_t* resp_stream);
  zenoh_rpc::RpcStatus handle_EchoMalloc(pb_istream_t* req_stream, pb_ostream_t* resp_stream);
  zenoh_rpc::RpcStatus handle_StartSensorStream(pb_istream_t* req_stream, pb_ostream_t* resp_stream);
  zenoh_rpc::RpcStatus handle_StopSensorStream(pb_istream_t* req_stream, pb_ostream_t* resp_stream);
  zenoh_rpc::RpcStatus handle_ConfigureWifi(pb_istream_t* req_stream, pb_ostream_t* resp_stream);
};

}  // namespace practice::rpc
#endif  // SERVICE_SERVER_H