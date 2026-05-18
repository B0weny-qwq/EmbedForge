#include "stm32f1xx.h"

uint32_t SystemCoreClock = 8000000U;
const uint8_t AHBPrescTable[16] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 6, 7, 8, 9};
const uint8_t APBPrescTable[8] = {0, 0, 0, 0, 1, 2, 3, 4};

void SystemInit(void)
{
  RCC->CR |= RCC_CR_HSION;
  RCC->CFGR = 0x00000000U;
  RCC->CR &= ~(RCC_CR_HSEON | RCC_CR_CSSON | RCC_CR_PLLON);
  RCC->CR &= ~RCC_CR_HSEBYP;
  RCC->CFGR &= ~RCC_CFGR_PLLMULL;
  RCC->CFGR &= ~RCC_CFGR_PLLSRC;
  RCC->CIR = 0x009F0000U;
}

void SystemCoreClockUpdate(void)
{
  SystemCoreClock = 8000000U;
}
