#include "ti_msp_dl_config.h"

/* LP_MSPM0G3507 USER_LED_1 is GPIOB.22, pinCMx 50.
 * 32 MHz CPU clock, roughly 0.5 s per delay. */
#define BLINK_DELAY_CYCLES (16000000U)
#define BLINK_PORT GPIO_LEDS_PORT
#define BLINK_PIN  GPIO_LEDS_USER_LED_1_PIN

int main(void)
{
    SYSCFG_DL_init();

    DL_GPIO_setPins(BLINK_PORT, BLINK_PIN);

    while (1) {
        delay_cycles(BLINK_DELAY_CYCLES);
        DL_GPIO_togglePins(BLINK_PORT, BLINK_PIN);
    }
}
