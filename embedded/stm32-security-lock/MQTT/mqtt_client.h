/* Agent 4 — STM32F103 không có WiFi: ESP32 giữ kết nối MQTT và chuyển tiếp payload qua UART */
#ifndef MQTT_CLIENT_H
#define MQTT_CLIENT_H
typedef enum { DECISION_GRANTED, DECISION_DENIED, DECISION_UNKNOWN } Decision_t;
Decision_t Parse_Decision(const char *payload);
#endif
