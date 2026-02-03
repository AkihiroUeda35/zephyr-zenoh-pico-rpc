#include <zephyr/logging/log.h>

#define LOG_DEBUG(...) LOG_DBG(__VA_ARGS__)
#define LOG_INFO(...) LOG_INF(__VA_ARGS__)
#define LOG_WARNING(...) LOG_WRN(__VA_ARGS__)
#define LOG_ERROR(...) LOG_ERR(__VA_ARGS__)

#define __print(...) printk(__VA_ARGS__)
// #define __print(...)