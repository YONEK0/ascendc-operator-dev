#include "kernel_operator.h"
#include "adaptive_avg_pool2d_grad_tiling.h"
#ifndef __CCE_KT_TEST__
#include "tiling_key_adaptive_avg_pool2d_grad.h"
#endif

using namespace AscendC;

template<typename T>
__aicore__ inline T dev_min(T a, T b) {
    return a < b ? a : b;
}

template<typename T>
__aicore__ inline T dev_max(T a, T b) {
    return a > b ? a : b;
}

class KernelAdaptiveAvgPool2dGrad {
public:
    __aicore__ inline KernelAdaptiveAvgPool2dGrad() {}

    __aicore__ inline void Init(GM_ADDR grad_output, GM_ADDR grad_input, const AdaptiveAvgPool2dGradTilingData* tiling) {
        tiling_ = *tiling;
        uint32_t block_idx = GetBlockIdx();
        uint32_t tasks = tiling_.tasksPerCore + (block_idx < tiling_.extraTasks ? 1 : 0);
        uint32_t start_blk = block_idx * tiling_.tasksPerCore + dev_min(block_idx, tiling_.extraTasks);

        myStartIdx_ = start_blk * tiling_.alignBlockSize;
        myEndIdx_ = dev_min((start_blk + tasks) * tiling_.alignBlockSize, tiling_.totalGradInputSize);

        gradOutputGm_.SetGlobalBuffer((__gm__ float*)grad_output);
        gradInputGm_.SetGlobalBuffer((__gm__ float*)grad_input);

        pipe_.InitBuffer(inBuf_, 4096 * sizeof(float));
        pipe_.InitBuffer(outBuf_, 512 * sizeof(float));

        cached_row_ = 0xFFFFFFFF;
        cached_in_ptr_ = nullptr;
    }

    __aicore__ inline void Process() {
        if (myStartIdx_ >= myEndIdx_) return;

        LocalTensor<float> outLocal = outBuf_.Get<float>();
        LocalTensor<float> inLocal = inBuf_.Get<float>();
        uint32_t chunkSize = 256;

        uint32_t H = tiling_.H_in;
        uint32_t W = tiling_.W_in;
        uint32_t H_out = tiling_.H_out;
        uint32_t W_out = tiling_.W_out;
        uint64_t HW = (uint64_t)H * W;

        for (uint32_t curr = myStartIdx_; curr < myEndIdx_; curr += chunkSize) {
            uint32_t curNum = dev_min(chunkSize, myEndIdx_ - curr);
            uint32_t curNumAlign = (curNum + 7) & (~7);

            for (uint32_t k = 0; k < curNumAlign; ++k) {
                outLocal.SetValue(k, 0.0f);
            }

            for (uint32_t k = 0; k < curNum; ++k) {
                uint64_t idx = curr + k;
                uint32_t c = (uint32_t)(idx / HW);
                uint64_t rem = idx % HW;
                uint32_t h = (uint32_t)(rem / W);
                uint32_t w = (uint32_t)(rem % W);

                uint32_t oh_start = (uint32_t)(((uint64_t)h * H_out) / H);
                uint32_t oh_end = (uint32_t)(((uint64_t)(h + 1) * H_out + H - 1) / H);
                uint32_t ow_start = (uint32_t)(((uint64_t)w * W_out) / W);
                uint32_t ow_end = (uint32_t)(((uint64_t)(w + 1) * W_out + W - 1) / W);

                float sum_val = 0.0f;

                for (uint32_t i = oh_start; i < oh_end; ++i) {
                    uint32_t target_row = c * H_out + i;
                    EnsureLineCached(target_row, W_out, inLocal);

                    int32_t hs = (int32_t)(((int64_t)i * H) / H_out);
                    int32_t he = (int32_t)(((int64_t)(i + 1) * H + H_out - 1) / H_out);
                    int32_t win_h = he - hs;
                    float inv_h = 1.0f / (float)win_h;

                    for (uint32_t j = ow_start; j < ow_end; ++j) {
                        int32_t ws = (int32_t)(((int64_t)j * W) / W_out);
                        int32_t we = (int32_t)(((int64_t)(j + 1) * W + W_out - 1) / W_out);
                        int32_t win_w = we - ws;
                        float inv_w = 1.0f / (float)win_w;

                        float g_val = cached_in_ptr_[j];
                        sum_val += g_val * (inv_h * inv_w);
                    }
                }
                outLocal.SetValue(k, sum_val);
            }

            PipeBarrier<PIPE_V>();
            DataCopy(gradInputGm_[curr], outLocal, curNumAlign);
            PipeBarrier<PIPE_MTE3>();
        }
    }

private:
    __aicore__ inline void EnsureLineCached(uint32_t row, uint32_t W_out, LocalTensor<float>& inLocal) {
        if (cached_row_ == row) return;

        uint64_t gm_row_offset = (uint64_t)row * W_out;
        uint64_t addr_bytes = gm_row_offset * sizeof(float);
        uint64_t aligned_addr_bytes = (addr_bytes / 32) * 32;
        uint64_t head_skip_bytes = addr_bytes - aligned_addr_bytes;
        uint32_t head_skip_elems = (uint32_t)(head_skip_bytes / sizeof(float));

        uint32_t read_bytes = (uint32_t)(head_skip_bytes + W_out * sizeof(float));
        uint32_t copy_bytes = ((read_bytes + 31) / 32) * 32;
        uint32_t copy_elems = copy_bytes / sizeof(float);

        DataCopy(inLocal, gradOutputGm_[aligned_addr_bytes / sizeof(float)], copy_elems);
        PipeBarrier<PIPE_MTE2>();

        cached_in_ptr_ = ((__ubuf__ float*)inLocal.GetPhyAddr()) + head_skip_elems;
        cached_row_ = row;
    }

    TPipe pipe_;
    TBuf<TPosition::VECCALC> inBuf_;
    TBuf<TPosition::VECCALC> outBuf_;

    GlobalTensor<float> gradOutputGm_;
    GlobalTensor<float> gradInputGm_;

    AdaptiveAvgPool2dGradTilingData tiling_;
    uint32_t myStartIdx_;
    uint32_t myEndIdx_;
    uint32_t cached_row_;
    __ubuf__ float* cached_in_ptr_;
};

extern "C" __global__ __aicore__ void adaptive_avg_pool2d_grad(
    GM_ADDR grad_output,
    GM_ADDR grad_input,
    GM_ADDR workspace,
    GM_ADDR tiling) {
    GET_TILING_DATA(tilingData, tiling);
    KernelAdaptiveAvgPool2dGrad op;
    op.Init(grad_output, grad_input, &tilingData);
    op.Process();
}
