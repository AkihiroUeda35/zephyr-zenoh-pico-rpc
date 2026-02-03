cmake_minimum_required(VERSION 3.20)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(zenoh_rpc)

# Workaround for Zephyr 4.x sysconf.h / picolibc compatibility issue
# Add missing POSIX limit definitions

zephyr_compile_definitions(
    _POSIX_RE_DUP_MAX=255
    _POSIX_SS_REPL_MAX=4
    _POSIX_TRACE_NAME_MAX=8
    _POSIX_TRACE_SYS_MAX=8
    _POSIX_TRACE_USER_EVENT_MAX=32
    _POSIX2_BC_BASE_MAX=99
    _POSIX2_BC_DIM_MAX=2048
    _POSIX2_BC_SCALE_MAX=99
    _POSIX2_BC_STRING_MAX=1000
    _POSIX2_COLL_WEIGHTS_MAX=2
    _POSIX2_EXPR_NEST_MAX=32
    _POSIX_AIO_LISTIO_MAX=2
    _POSIX_AIO_MAX=1
    _POSIX_ARG_MAX=4096
    _POSIX_CHILD_MAX=25
    _POSIX_LOGIN_NAME_MAX=9
    _POSIX_NGROUPS_MAX=8
    _POSIX_MQ_PRIO_MAX=32
    _POSIX_THREAD_DESTRUCTOR_ITERATIONS=4
    _POSIX_SIGQUEUE_MAX=32
    _POSIX_STREAM_MAX=16
    _POSIX_SYMLOOP_MAX=16
    _POSIX_TTY_NAME_MAX=9
    _POSIX_TZNAME_MAX=6
)

# Overwrite compile option with custom zenoh-generic config
zephyr_compile_definitions(ZENOH_GENERIC)
zephyr_include_directories(${CMAKE_CURRENT_SOURCE_DIR})

# Add Zenoh log
zephyr_compile_definitions(ZENOH_DEBUG=3 ZENOH_LOG_TRACE ZENOH_LOG_PRINT=printk)

target_sources(app PRIVATE
    main.cpp
    service_impl.cpp
    rpc/service.pb.c
    rpc/zenoh_rpc_channel.cpp
    rpc/zenoh_pubsub.cpp
    rpc/service_server.cpp
    wifi/wifi_manager.cpp
)

# Include directories
target_include_directories(app PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/rpc
    ${CMAKE_CURRENT_SOURCE_DIR}/wifi
)