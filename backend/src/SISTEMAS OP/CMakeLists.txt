cmake_minimum_required(VERSION 3.15)
project(OSSimulator CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Compiler warnings
if(MSVC)
    add_compile_options(/W3 /wd4996)
else()
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Release build optimizations (default Debug for dev)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif()

# Include paths
include_directories(
    ${CMAKE_SOURCE_DIR}/include
    ${CMAKE_SOURCE_DIR}/src
)

# Source files
set(SOURCES
    src/main.cpp
    src/scheduler.cpp
    src/dispatcher.cpp
    src/memory_manager.cpp
    src/io_manager.cpp
    src/error_manager.cpp
    src/json_reader.cpp
    src/json_writer.cpp
    src/simulator.cpp
)

add_executable(simulator ${SOURCES})

# Copy scenario file to build directory for easy testing
configure_file(
    ${CMAKE_SOURCE_DIR}/escenario_modelo.json
    ${CMAKE_BINARY_DIR}/escenario_modelo.json
    COPYONLY
)

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "CXX Standard: ${CMAKE_CXX_STANDARD}")
