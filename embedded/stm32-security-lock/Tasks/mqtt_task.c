/* Agent 4 (GIAI ĐOẠN 2) — Nhận {"decision":...} từ ESP32 qua UART, gửi vào Queue */
#include "FreeRTOS.h"
#include "task.h"
void MqttTask(void *arg) { for (;;) { vTaskDelay(pdMS_TO_TICKS(50)); } }
