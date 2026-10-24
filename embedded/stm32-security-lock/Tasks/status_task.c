/* Agent 4 (GIAI ĐOẠN 2) — Gửi trạng thái khóa/cửa định kỳ */
#include "FreeRTOS.h"
#include "task.h"
void StatusTask(void *arg) { for (;;) { vTaskDelay(pdMS_TO_TICKS(50)); } }
