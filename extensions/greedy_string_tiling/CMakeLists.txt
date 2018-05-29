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

set(GOOGLE_BENCHMARK_LIBS /usr/local/lib)
set(GOOGLE_BENCHMARK_INCLUDES /usr/local/include)
set(CATCH2_HEADER_DIR $ENV{HOME}/cpp-scribble/Catch2/single_include)
set(TESTS_EXECUTABLE run_tests)
set(TESTS_SOURCES tests/test_matcher.cpp include/gst.hpp ${CATCH2_HEADER_DIR}/catch.hpp)

set(BENCHMARK_EXECUTABLE run_benchmark)
set(BENCHMARK_SOURCES tests/test_benchmark.cpp include/gst.hpp ${GOOGLE_BENCHMARK_INCLUDES})

set(CMAKE_THREAD_PREFER_PTHREAD TRUE)
set(THREADS_PREFER_PTHREAD_FLAG TRUE)
find_package(Threads REQUIRED)

add_executable(${TESTS_EXECUTABLE} ${TESTS_SOURCES})
add_executable(${BENCHMARK_EXECUTABLE} ${BENCHMARK_SOURCES})

target_link_libraries(${TESTS_EXECUTABLE} Matcher)
target_link_libraries(${BENCHMARK_EXECUTABLE}
    Threads::Threads
    Matcher
    ${GOOGLE_BENCHMARK_LIBS}/libbenchmark.a
    ${GOOGLE_BENCHMARK_LIBS}/libbenchmark_main.a)

target_include_directories(Matcher PRIVATE include)
target_include_directories(${TESTS_EXECUTABLE} PRIVATE
    ${CATCH2_HEADER_DIR}
    include)
target_include_directories(${BENCHMARK_EXECUTABLE} PRIVATE
    ${GOOGLE_BENCHMARK_INCLUDES}
    include)


