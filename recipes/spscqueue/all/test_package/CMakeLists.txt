cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

find_package(SPSCQueue REQUIRED CONFIG)
find_package(Threads REQUIRED)

add_executable(${PROJECT_NAME} test_package.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE SPSCQueue::SPSCQueue Threads::Threads)
target_compile_features(${PROJECT_NAME} PRIVATE cxx_std_11)
