#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
void app_main(void)
{
    unsigned count = 0;
    for (;;) {
        ESP_LOGI("HUNINN_ANDROID", "Projeto criado no celular: %u", count++);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}
