// Device Service Implementation

#pragma once

#include <zephyr/logging/log.h>

#include "rpc/service_server.h"
#include "rpc/zenoh_pubsub.h"
#include "service.pb.h"

namespace practice::rpc {

class DeviceServiceImpl : public DeviceService {
 public:
  DeviceServiceImpl(
      zenoh_rpc::TelemetryPublisher<practice_rpc_SensorTelemetry>* sensor_pub,
      zenoh_rpc::LogPublisher* log_pub)
      : sensor_pub_(sensor_pub), log_pub_(log_pub), streaming_enabled_(false) {}

  zenoh_rpc::RpcStatus SetLed(const practice_rpc_LedRequest& request,
                              practice_rpc_LedResponse* response) override;

  zenoh_rpc::RpcStatus Echo(const practice_rpc_EchoRequest& request,
                            practice_rpc_EchoResponse* response) override;

  zenoh_rpc::RpcStatus EchoMalloc(
      const practice_rpc_EchoRequestMalloc& request,
      practice_rpc_EchoResponseMalloc* response) override;

  zenoh_rpc::RpcStatus StartSensorStream(
      const practice_rpc_SensorRequest& request,
      practice_rpc_Empty* response) override;

  zenoh_rpc::RpcStatus StopSensorStream(const practice_rpc_Empty& request,
                                        practice_rpc_Empty* response) override;

  zenoh_rpc::RpcStatus ConfigureWifi(const practice_rpc_WifiSettings& request,
                                     practice_rpc_Empty* response) override;

  // Called periodically from sensor task to publish telemetry
  void publish_sensor_data();

  // Check if streaming is enabled
  bool is_streaming_enabled() const { return streaming_enabled_; }

 private:
  zenoh_rpc::TelemetryPublisher<practice_rpc_SensorTelemetry>* sensor_pub_;
  zenoh_rpc::LogPublisher* log_pub_;
  bool streaming_enabled_;
};

}  // namespace practice::rpc
