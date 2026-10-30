# ----------------------------------------------------------------------------------------------------------
# op_host/CMakeLists.txt - 编译 Host 侧算子定义与 Tiling
# ----------------------------------------------------------------------------------------------------------

set(host_ops_srcs
    ${CMAKE_CURRENT_SOURCE_DIR}/adaptive_avg_pool2d_grad.cpp
)

npu_op_library(cust_optiling TILING
    ${host_ops_srcs}
)

target_include_directories(cust_optiling PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../op_kernel
    $ENV{ASCEND_HOME_PATH}/include
    $ENV{ASCEND_HOME_PATH}/asc/include/tiling
    $ENV{ASCEND_HOME_PATH}/pkg_inc
    $ENV{ASCEND_HOME_PATH}/pkg_inc/op_common
    $ENV{ASCEND_HOME_PATH}/pkg_inc/base
)

set(SECURE_COMPILE_OPTIONS -fPIC -fstack-protector-all)
set(SECURE_LINK_OPTIONS -Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack)

target_compile_options(cust_optiling PRIVATE ${SECURE_COMPILE_OPTIONS})
target_link_options(cust_optiling PRIVATE ${SECURE_LINK_OPTIONS})

npu_op_package_add(${package_name}
    LIBRARY
        cust_optiling
)
