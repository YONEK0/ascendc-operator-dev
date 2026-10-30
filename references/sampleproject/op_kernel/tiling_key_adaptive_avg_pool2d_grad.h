#ifndef TILING_KEY_ADAPTIVE_AVG_POOL2D_GRAD_H
#define TILING_KEY_ADAPTIVE_AVG_POOL2D_GRAD_H

#include <cstdint>

/**
 * @brief TilingKey 分发枚举
 * 用于在 Kernel 入口处快速分发不同数据精度或不同优化路径
 */
enum class AdaptiveAvgPool2dGradTilingKey : uint64_t {
    FP32_DEFAULT = 0,
    FP16_DEFAULT = 1,
    BF16_DEFAULT = 2,
    FP32_ALIGNED = 10,
    FP32_UNALIGNED = 11
};

#endif // TILING_KEY_ADAPTIVE_AVG_POOL2D_GRAD_H
