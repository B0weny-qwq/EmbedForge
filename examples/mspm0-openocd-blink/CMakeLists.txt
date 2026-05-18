cmake_minimum_required(VERSION 3.20)
project(mspm0-openocd-blink C ASM)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT DEFINED MSPM0_SDK_PATH)
  if(DEFINED ENV{MSPM0_SDK_PATH})
    set(MSPM0_SDK_PATH "$ENV{MSPM0_SDK_PATH}")
  else()
    set(MSPM0_SDK_PATH "$ENV{HOME}/SDK/TI/mspm0-sdk")
  endif()
endif()

set(SDK "${MSPM0_SDK_PATH}")
set(DRIVERLIB "${SDK}/source/ti/driverlib/lib/gcc/m0p/mspm0g1x0x_g3x0x/driverlib.a")
set(LINKER_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/linker/mspm0g3507.lds")

add_executable(app.elf
  Core/Src/main.c
  Core/Src/ti_msp_dl_config.c
  Startup/startup_mspm0g350x_gcc.c
)

target_include_directories(app.elf PRIVATE
  Core/Inc
  ${SDK}/source
  ${SDK}/source/third_party/CMSIS/Core/Include
)

target_compile_definitions(app.elf PRIVATE __MSPM0G3507__)

target_compile_options(app.elf PRIVATE
  -mcpu=cortex-m0plus
  -march=armv6-m
  -mthumb
  -mfloat-abi=soft
  -std=c99
  -ffunction-sections
  -fdata-sections
  -g
  -gstrict-dwarf
  -Wall
  -O2
)

target_link_options(app.elf PRIVATE
  -mcpu=cortex-m0plus
  -march=armv6-m
  -mthumb
  -mfloat-abi=soft
  -nostartfiles
  -static
  -Wl,--gc-sections
  -Wl,-T,${LINKER_SCRIPT}
  -Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/app.map
  --specs=nano.specs
  --specs=nosys.specs
)

target_link_libraries(app.elf PRIVATE
  ${DRIVERLIB}
  gcc
  c
  m
)

add_custom_command(TARGET app.elf POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:app.elf> ${CMAKE_CURRENT_BINARY_DIR}/app.hex
  COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:app.elf> ${CMAKE_CURRENT_BINARY_DIR}/app.bin
  COMMAND ${CMAKE_SIZE} $<TARGET_FILE:app.elf>
)
