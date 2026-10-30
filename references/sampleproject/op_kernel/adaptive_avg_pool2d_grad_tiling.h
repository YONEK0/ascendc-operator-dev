#ifndef ADAPTIVE_AVG_POOL2D_GRAD_TILING_H
#define ADAPTIVE_AVG_POOL2D_GRAD_TILING_H

#include <cstdint>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Host 与 Kernel 之间的唯一数据契约 (POD 结构体)
 * 必须保持 8 字节/4 字节对齐，不包含指针或 C++ 容器
 */
struct AdaptiveAvgPool2dGradTilingData {
    uint32_t totalTaskNum;    // 总处理任务单元数（例如总输出元素数按 32B 块切分）
    uint32_t tasksPerCore;    // 每个 AI Core 处理的基础任务数
    uint32_t extraTasks;      // 余数任务数（分配给前 extraTasks 个核）
    uint32_t alignBlockSize;  // 32B 对齐块大小（float 为 8 个元素）

    uint32_t N;               // Batch 尺寸
    uint32_t C;               // 通道数
    uint32_t H_in;            // 输入特征图高度
    uint32_t W_in;            // 输入特征图宽度
    uint32_t H_out;           // 输出特征图高度
    uint32_t W_out;           // 输出特征图宽度

    uint32_t totalGradInputSize;  // 输出张量总元素数 (N * C * H_in * W_in)
    uint32_t totalGradOutputSize; // 输入张量总元素数 (N * C * H_out * W_out)
};

#ifdef __cplusplus
}
#endif

#ifndef __aicore__
#define __aicore__
#endif

#ifndef __gm__
#define __gm__
#endif

#ifndef GET_TILING_DATA
__aicore__ inline void CopyTilingData(AdaptiveAvgPool2dGradTilingData& dst, __gm__ const AdaptiveAvgPool2dGradTilingData* src) {
    dst.totalTaskNum = src->totalTaskNum;
    dst.tasksPerCore = src->tasksPerCore;
    dst.extraTasks = src->extraTasks;
    dst.alignBlockSize = src->alignBlockSize;
    dst.N = src->N;
    dst.C = src->C;
    dst.H_in = src->H_in;
    dst.W_in = src->W_in;
    dst.H_out = src->H_out;
    dst.W_out = src->W_out;
    dst.totalGradInputSize = src->totalGradInputSize;
    dst.totalGradOutputSize = src->totalGradOutputSize;
}

#define GET_TILING_DATA(tdata, ptr) \
    AdaptiveAvgPool2dGradTilingData tdata; \
    CopyTilingData(tdata, (__gm__ const AdaptiveAvgPool2dGradTilingData*)(ptr))
#endif

#ifndef GET_TILING_DATA_WITH_STRUCT
#define GET_TILING_DATA_WITH_STRUCT(T, tdata, ptr) GET_TILING_DATA(tdata, ptr)
#endif

#endif // ADAPTIVE_AVG_POOL2D_GRAD_TILING_H
