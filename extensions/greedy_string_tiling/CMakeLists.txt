# You don't need this file for installing the Python extension as
# its build process is handled by setuptools.
# This file exists for development purposes, e.g. compiling the Catch2 unit tests for testing the cpp implementation.
cmake_minimum_required(VERSION 3.5)
project(GreedyStringTiling)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pedantic")
set(CMAKE_EXPORT_COMPILE_COMMANDS ON) # for editor auto completer

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

set(MATCHER_SOURCES src/gst.cpp include/gst.hpp)
add_library(Matcher ${MATCHER_SOURCES})

set(CATCH2_HEADER_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../Catch2/single_include)
set(TESTS_EXECUTABLE run_tests)
set(TESTS_SOURCES tests/test_matcher.cpp include/gst.hpp ${CATCH2_HEADER_DIR}/catch.hpp)

add_executable(${TESTS_EXECUTABLE} ${TESTS_SOURCES})
target_link_libraries(${TESTS_EXECUTABLE} Matcher)
target_include_directories(Matcher PRIVATE include)
target_include_directories(${TESTS_EXECUTABLE} PRIVATE
    ${CATCH2_HEADER_DIR}
    include)

