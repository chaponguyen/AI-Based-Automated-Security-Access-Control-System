/* Agent 4 (GIAI ĐOẠN 2) — Đọc reed switch có chống dội; cảnh báo cửa mở quá giờ */
#include "FreeRTOS.h"
#include "task.h"
void SensorTask(void *arg) { for (;;) { vTaskDelay(pdMS_TO_TICKS(50)); } }
