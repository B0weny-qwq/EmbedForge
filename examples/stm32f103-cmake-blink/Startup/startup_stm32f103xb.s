.syntax unified
.cpu cortex-m3
.thumb

.global g_pfnVectors
.global Reset_Handler

.section .text.Reset_Handler
.weak Reset_Handler
.type Reset_Handler, %function
Reset_Handler:
  ldr r0, =_estack
  mov sp, r0

  ldr r0, =_sdata
  ldr r1, =_edata
  ldr r2, =_sidata
CopyData:
  cmp r0, r1
  bcc CopyDataWord
  b ZeroBss
CopyDataWord:
  ldr r3, [r2], #4
  str r3, [r0], #4
  b CopyData

ZeroBss:
  ldr r0, =_sbss
  ldr r1, =_ebss
  movs r2, #0
ZeroBssLoop:
  cmp r0, r1
  bcc ZeroBssWord
  b CallMain
ZeroBssWord:
  str r2, [r0], #4
  b ZeroBssLoop

CallMain:
  bl SystemInit
  bl main
LoopForever:
  b LoopForever

.size Reset_Handler, .-Reset_Handler

.section .text.Default_Handler,"ax",%progbits
.type Default_Handler, %function
.thumb_func
Default_Handler:
  b Default_Handler
.size Default_Handler, .-Default_Handler

.macro IRQ handler
  .weak \handler
  .set \handler, Default_Handler
.endm

IRQ NMI_Handler
IRQ HardFault_Handler
IRQ MemManage_Handler
IRQ BusFault_Handler
IRQ UsageFault_Handler
IRQ SVC_Handler
IRQ DebugMon_Handler
IRQ PendSV_Handler
IRQ SysTick_Handler
IRQ WWDG_IRQHandler
IRQ PVD_IRQHandler
IRQ TAMPER_IRQHandler
IRQ RTC_IRQHandler
IRQ FLASH_IRQHandler
IRQ RCC_IRQHandler
IRQ EXTI0_IRQHandler
IRQ EXTI1_IRQHandler
IRQ EXTI2_IRQHandler
IRQ EXTI3_IRQHandler
IRQ EXTI4_IRQHandler
IRQ DMA1_Channel1_IRQHandler
IRQ DMA1_Channel2_IRQHandler
IRQ DMA1_Channel3_IRQHandler
IRQ DMA1_Channel4_IRQHandler
IRQ DMA1_Channel5_IRQHandler
IRQ DMA1_Channel6_IRQHandler
IRQ DMA1_Channel7_IRQHandler
IRQ ADC1_2_IRQHandler
IRQ USB_HP_CAN1_TX_IRQHandler
IRQ USB_LP_CAN1_RX0_IRQHandler
IRQ CAN1_RX1_IRQHandler
IRQ CAN1_SCE_IRQHandler
IRQ EXTI9_5_IRQHandler
IRQ TIM1_BRK_IRQHandler
IRQ TIM1_UP_IRQHandler
IRQ TIM1_TRG_COM_IRQHandler
IRQ TIM1_CC_IRQHandler
IRQ TIM2_IRQHandler
IRQ TIM3_IRQHandler
IRQ TIM4_IRQHandler
IRQ I2C1_EV_IRQHandler
IRQ I2C1_ER_IRQHandler
IRQ I2C2_EV_IRQHandler
IRQ I2C2_ER_IRQHandler
IRQ SPI1_IRQHandler
IRQ SPI2_IRQHandler
IRQ USART1_IRQHandler
IRQ USART2_IRQHandler
IRQ USART3_IRQHandler
IRQ EXTI15_10_IRQHandler
IRQ RTC_Alarm_IRQHandler
IRQ USBWakeUp_IRQHandler

.section .isr_vector,"a",%progbits
.type g_pfnVectors, %object
g_pfnVectors:
  .word _estack
  .word Reset_Handler
  .word NMI_Handler
  .word HardFault_Handler
  .word MemManage_Handler
  .word BusFault_Handler
  .word UsageFault_Handler
  .word 0
  .word 0
  .word 0
  .word 0
  .word SVC_Handler
  .word DebugMon_Handler
  .word 0
  .word PendSV_Handler
  .word SysTick_Handler
  .word WWDG_IRQHandler
  .word PVD_IRQHandler
  .word TAMPER_IRQHandler
  .word RTC_IRQHandler
  .word FLASH_IRQHandler
  .word RCC_IRQHandler
  .word EXTI0_IRQHandler
  .word EXTI1_IRQHandler
  .word EXTI2_IRQHandler
  .word EXTI3_IRQHandler
  .word EXTI4_IRQHandler
  .word DMA1_Channel1_IRQHandler
  .word DMA1_Channel2_IRQHandler
  .word DMA1_Channel3_IRQHandler
  .word DMA1_Channel4_IRQHandler
  .word DMA1_Channel5_IRQHandler
  .word DMA1_Channel6_IRQHandler
  .word DMA1_Channel7_IRQHandler
  .word ADC1_2_IRQHandler
  .word USB_HP_CAN1_TX_IRQHandler
  .word USB_LP_CAN1_RX0_IRQHandler
  .word CAN1_RX1_IRQHandler
  .word CAN1_SCE_IRQHandler
  .word EXTI9_5_IRQHandler
  .word TIM1_BRK_IRQHandler
  .word TIM1_UP_IRQHandler
  .word TIM1_TRG_COM_IRQHandler
  .word TIM1_CC_IRQHandler
  .word TIM2_IRQHandler
  .word TIM3_IRQHandler
  .word TIM4_IRQHandler
  .word I2C1_EV_IRQHandler
  .word I2C1_ER_IRQHandler
  .word I2C2_EV_IRQHandler
  .word I2C2_ER_IRQHandler
  .word SPI1_IRQHandler
  .word SPI2_IRQHandler
  .word USART1_IRQHandler
  .word USART2_IRQHandler
  .word USART3_IRQHandler
  .word EXTI15_10_IRQHandler
  .word RTC_Alarm_IRQHandler
  .word USBWakeUp_IRQHandler
.size g_pfnVectors, .-g_pfnVectors
