/* Agent 4 (GIAI ĐOẠN 2) — granted: LED xanh + relay mở 10 giây rồi tự đóng; denied: LED đỏ + buzzer, KHÔNG chạm relay */
#include "FreeRTOS.h"
#include "task.h"
void DoorTask(void *arg) { for (;;) { vTaskDelay(pdMS_TO_TICKS(50)); } }
