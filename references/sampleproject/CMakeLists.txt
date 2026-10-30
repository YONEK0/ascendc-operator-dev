# ----------------------------------------------------------------------------------------------------------
# Sample Project: Custom Operator Project Template
# 标准自定义算子结构，自带本机测试驱动 main_test.asc
# ----------------------------------------------------------------------------------------------------------

cmake_minimum_required(VERSION 3.16.0)
set(CMAKE_ASC_ARCHITECTURES "dav-2201" CACHE STRING "Target architecture")
set(CMAKE_ASC_RUN_MODE "npu" CACHE STRING "npu or cpu")

# 必须先 find_package(ASC REQUIRED)，才能在 project 中启用 ASC 语言
find_package(ASC REQUIRED)

project(sample_custom_prj LANGUAGES ASC CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT DEFINED CANNJUDGE_COMPILE_JOBS)
    set(CANNJUDGE_COMPILE_JOBS 4)
endif()

set(ASCEND_COMPUTE_UNIT ascend910b)

set(package_name custom)

npu_op_package(${package_name}
    TYPE RUN
    CONFIG
        INSTALL_PATH ${CMAKE_BINARY_DIR}
)

add_subdirectory(op_host)
add_subdirectory(op_kernel)

# 编译真机测试驱动 test_op (调用 op_kernel 和 op_host 实现端到端真机验证)
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/main_test.asc")
    add_executable(test_op main_test.asc)
    target_include_directories(test_op PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/op_kernel
        ${CMAKE_CURRENT_SOURCE_DIR}/op_host
    )
    target_compile_options(test_op PRIVATE
        $<$<COMPILE_LANGUAGE:ASC>:--npu-arch=${CMAKE_ASC_ARCHITECTURES}>)
    target_link_libraries(test_op PRIVATE
        tiling_api register platform unified_dlog dl m graph_base ascendcl)
endif()
