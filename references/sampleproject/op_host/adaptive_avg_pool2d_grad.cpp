#include "register/op_def_registry.h"
#include "tiling/platform/platform_ascendc.h"
#include "../op_kernel/adaptive_avg_pool2d_grad_tiling.h"

namespace optiling {

static ge::graphStatus TilingFunc(gert::TilingContext* context) {
    if (context == nullptr) {
        return ge::GRAPH_FAILED;
    }

    auto gradOutputShape = context->GetInputShape(0);
    if (gradOutputShape == nullptr) {
        return ge::GRAPH_FAILED;
    }

    // 获取输入输出形状
    // 假设输入 grad_output 为 [N, C, H_out, W_out]
    // 假定通过属性或输入推导输入图尺寸 [N, C, H_in, W_in]
    auto shapeDims = gradOutputShape->GetStorageShape();
    uint32_t N = (uint32_t)shapeDims.GetDim(0);
    uint32_t C = (uint32_t)shapeDims.GetDim(1);
    uint32_t H_out = (uint32_t)shapeDims.GetDim(2);
    uint32_t W_out = (uint32_t)shapeDims.GetDim(3);

    // 从属性或第二个输入获取 orig_input_shape (H_in, W_in)
    // 默认或从 context 读取，此处给出通用示范
    uint32_t H_in = H_out;
    uint32_t W_in = W_out;
    auto attrs = context->GetAttrs();
    if (attrs != nullptr) {
        auto orig_h = attrs->GetAttrPointer<int64_t>(0);
        auto orig_w = attrs->GetAttrPointer<int64_t>(1);
        if (orig_h != nullptr) H_in = (uint32_t)(*orig_h);
        if (orig_w != nullptr) W_in = (uint32_t)(*orig_w);
    }

    uint32_t totalGradInputSize = N * C * H_in * W_in;
    uint32_t totalGradOutputSize = N * C * H_out * W_out;

    // 平台硬件核心数获取
    auto ascendcPlatform = platform_ascendc::PlatformAscendC(context->GetPlatformInfo());
    uint32_t aicCoreNum = ascendcPlatform.GetCoreNum();
    if (aicCoreNum == 0) {
        aicCoreNum = 8; // 安全默认 8 核
    }

    // 切分策略：以 32B (float 为 8 元素) 为不可分割的任务单元，保证无核间 cacheline 冲突
    const uint32_t ALIGN_ELEMS = 8;
    uint32_t totalBlocks = (totalGradInputSize + ALIGN_ELEMS - 1) / ALIGN_ELEMS;

    uint32_t usedCores = aicCoreNum;
    if (totalBlocks < usedCores) {
        usedCores = totalBlocks > 0 ? totalBlocks : 1;
    }

    uint32_t tasksPerCore = totalBlocks / usedCores;
    uint32_t extraTasks = totalBlocks % usedCores;

    AdaptiveAvgPool2dGradTilingData tilingData;
    tilingData.totalTaskNum = totalBlocks;
    tilingData.tasksPerCore = tasksPerCore;
    tilingData.extraTasks = extraTasks;
    tilingData.alignBlockSize = ALIGN_ELEMS;
    tilingData.N = N;
    tilingData.C = C;
    tilingData.H_in = H_in;
    tilingData.W_in = W_in;
    tilingData.H_out = H_out;
    tilingData.W_out = W_out;
    tilingData.totalGradInputSize = totalGradInputSize;
    tilingData.totalGradOutputSize = totalGradOutputSize;

    context->SetBlockDim(usedCores);

    auto rawTilingData = context->GetRawTilingData();
    if (rawTilingData == nullptr) {
        return ge::GRAPH_FAILED;
    }
    rawTilingData->InitData(sizeof(AdaptiveAvgPool2dGradTilingData));
    rawTilingData->CopyData((void*)&tilingData, sizeof(AdaptiveAvgPool2dGradTilingData));

    return ge::GRAPH_SUCCESS;
}

} // namespace optiling

namespace ops {

class AdaptiveAvgPool2dGrad : public OpDef {
public:
    explicit AdaptiveAvgPool2dGrad(const char* name) : OpDef(name) {
        this->Input("grad_output")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT, ge::DT_FLOAT16, ge::DT_BF16})
            .Format({ge::FORMAT_ND, ge::FORMAT_ND, ge::FORMAT_ND});

        this->Output("grad_input")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT, ge::DT_FLOAT16, ge::DT_BF16})
            .Format({ge::FORMAT_ND, ge::FORMAT_ND, ge::FORMAT_ND});

        this->Attr("orig_h").AttrType(OPTIONAL).Int(0);
        this->Attr("orig_w").AttrType(OPTIONAL).Int(0);

        this->AICore()
            .SetTiling(optiling::TilingFunc);

        this->AICore().AddConfig("ascend910b");
        this->AICore().AddConfig("ascend910_93");
        this->AICore().AddConfig("ascend950");
    }
};

OP_ADD(AdaptiveAvgPool2dGrad);

} // namespace ops
