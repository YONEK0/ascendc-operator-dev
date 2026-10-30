# ----------------------------------------------------------------------------------------------------------
# op_kernel/CMakeLists.txt - 编译 AI Core 算子核函数
# ----------------------------------------------------------------------------------------------------------

npu_op_kernel_sources(adaptive_avg_pool2d_grad_kernels
    OP_TYPE AdaptiveAvgPool2dGrad
    KERNEL_DIR .
    KERNEL_FILE adaptive_avg_pool2d_grad.cpp
)

npu_op_kernel_library(adaptive_avg_pool2d_grad_kernels
    SRC_BASE ${CMAKE_CURRENT_SOURCE_DIR}
    TILING_LIBRARY cust_optiling
)

npu_op_package_add(${package_name}
    LIBRARY
        adaptive_avg_pool2d_grad_kernels
)
