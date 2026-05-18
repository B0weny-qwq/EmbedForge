cmake_minimum_required(VERSION 3.20)

project(stm32f103-cmake-blink C ASM)

if(NOT DEFINED STM32CUBE_F1_PATH)
  if(DEFINED ENV{STM32CUBE_F1_PATH})
    set(STM32CUBE_F1_PATH "$ENV{STM32CUBE_F1_PATH}")
  else()
    set(STM32CUBE_F1_PATH "$ENV{HOME}/SDK/STM32/STM32CubeF1")
  endif()
endif()

set(SDK "${STM32CUBE_F1_PATH}")
set(LINKER_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/linker/STM32F103C8Tx_FLASH.ld")

add_executable(app.elf
  Core/Src/main.c
  Core/Src/stm32f1xx_hal_msp.c
  Core/Src/stm32f1xx_it.c
  Core/Src/system_stm32f1xx.c
  Startup/startup_stm32f103xb.s
  ${SDK}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c
  ${SDK}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_gpio.c
  ${SDK}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc.c
  ${SDK}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_cortex.c
  ${SDK}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_uart.c
  ${SDK}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_dma.c
)

target_include_directories(app.elf PRIVATE
  Core/Inc
  ${SDK}/Drivers/CMSIS/Include
  ${SDK}/Drivers/CMSIS/Device/ST/STM32F1xx/Include
  ${SDK}/Drivers/STM32F1xx_HAL_Driver/Inc
  ${SDK}/Drivers/STM32F1xx_HAL_Driver/Inc/Legacy
)

target_compile_definitions(app.elf PRIVATE STM32F103xB USE_HAL_DRIVER)

target_compile_options(app.elf PRIVATE
  -mcpu=cortex-m3
  -mthumb
  -ffunction-sections
  -fdata-sections
  -Wall
  -Wextra
  -Og
  -g3
)

target_link_options(app.elf PRIVATE
  -mcpu=cortex-m3
  -mthumb
  -T ${LINKER_SCRIPT}
  -Wl,--gc-sections
  -Wl,-Map=${CMAKE_BINARY_DIR}/app.map
  --specs=nano.specs
  --specs=nosys.specs
)

set_target_properties(app.elf PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}
)

add_custom_command(TARGET app.elf POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:app.elf> ${CMAKE_BINARY_DIR}/app.hex
  COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:app.elf> ${CMAKE_BINARY_DIR}/app.bin
  COMMAND ${CMAKE_SIZE} $<TARGET_FILE:app.elf>
  BYPRODUCTS ${CMAKE_BINARY_DIR}/app.hex ${CMAKE_BINARY_DIR}/app.bin
)
