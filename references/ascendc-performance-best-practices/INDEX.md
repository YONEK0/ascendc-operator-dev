# 性能优化知识索引

> 本索引只负责导航。具体优化方法以各 `guide.md` / `*_design.md` 为准。
> 开始前先读 [`SKILL.md`](SKILL.md) 的「优化顺序（先证瓶颈，再动手）」与「证据纪律」。

## 先读

- [主入口 SKILL.md](SKILL.md)：优化顺序、证据纪律、失败家族、算子族分类。
- [代际与验证范围](references/common/architecture-scope.md)：`arch22`（A2/A3，DAV_2201/220x）与 `arch35`（A5，DAV_3510）的适用范围。
- [模板源码查找与构建契约](references/common/template_usage.md)：模板选型、复制、构建预检。
- [VF 范例库](references/common/arch35/regbase/README.md)：arch35 的 Reg / MicroAPI / VF 参考。

## 按算子族

| 算子族 | 入口 | 适用架构 | 典型算子 |
|---|---|---|---|
| MatMul | [arch22 guide](references/matmul/arch22/guide.md) · [arch35 guide](references/matmul/arch35/guide.md) · [性能建模](references/matmul/arch35/performance_modeling.md) · [基本块](references/matmul/arch35/basic_block_design.md) · [Blaze 路线](references/matmul/arch35/blaze_design.md) | arch22 / arch35 | MatMul, BatchMatMul, GroupMatMul, MXFP4 |
| MC² 通算融合 | [guide](references/mc2/guide.md) | arch35 | matmul_all_reduce, allgather_matmul, matmul_reducescatter |
| FlashAttention | [arch22 guide](references/flash_attention/arch22/guide.md) · [arch35 guide](references/flash_attention/arch35/guide.md) · [通用优化](references/flash_attention/arch35/common-optimizations.md) · [CANNBot-DSL](references/flash_attention/arch35/cannbot-dsl/index.md) | arch22 / arch35 | FIA, FlashAttention, MLA, SparseFA |
| Sort / TopK | [arch22 基数排序](references/sort/arch22/radix_sort.md) · [arch35 模板](references/sort/arch35/templates/usage_guide.md) | arch22 / arch35 | TopK, Sort, ArgSort, ArgMax/Min |
| Reduction | [guide](references/reduce/guide.md) · [模板使用](references/reduce/templates/usage_guide.md) | arch35 | ReduceSum, Softmax, LayerNorm, RMSNorm |
| Scan / Cum | [guide](references/scan/guide.md) · [模板使用](references/scan/templates/usage_guide.md) | arch35 | Cumsum, Cummin, Cummax, Cumprod |
| Gather | [guide](references/gather/guide.md) · [模板使用](references/gather/templates/usage_guide.md) | arch35 | GatherV2, Embedding |
| Elementwise | [双缓冲](references/elementwise/double_buffer_design.md) · [向量化效率](references/elementwise/vector_efficiency_design.md) | arch35 | Sin, Cos, Abs, Exp |
| Broadcast | [总览](references/broadcast/broadcast_design.md) · [OneDim](references/broadcast/onedim_design.md) · [NDDMA](references/broadcast/nddma_design.md) · [DataCopyPad](references/broadcast/datacopypad_design.md) · [UB 广播](references/broadcast/ub_broadcast_design.md) · [进阶 Tiling](references/broadcast/advanced_tiling.md) | arch35 | Add, Mul, Sub 等含广播轴算子 |
| Scatter | [总览](references/scatter/scatter_design.md) · [元素并行](references/scatter/element_parallel_design.md) · [Fiber 独占](references/scatter/fiber_exclusive_design.md) · [通用 stride](references/scatter/generic_stride_design.md) · [精度与陷阱](references/scatter/precision_and_traps.md) · [Warp Last](references/scatter/warp_last_design.md) | arch35 | Scatter, ScatterAdd, ScatterReduce |
| Conversion | [guide](references/conversion/guide.md) · [Transpose 融合](references/conversion/transpose_fusion_design.md) | arch35 | Transpose, Concat, Split |
| Convolution | [guide](references/conv/guide.md) · [模板使用](references/conv/templates/usage_guide.md) | arch35 | Conv2D, DepthwiseConv, Conv3DDX, Conv3DDW |
| Scalar | [guide](references/common/scalar/guide.md) | arch22 / arch35 | 任意 ScalarBound 算子 |
| SIMT 进阶 | [优化指南](references/common/arch35/simt/optimization-guide.md) | arch35 | 条件分支、离散索引等不规则操作 |

## 按优化问题

| 问题 | 参考 |
|---|---|
| 数据搬运（DataCopy） | [arch22 数据搬运](references/common/arch22/datacopy_optimization_design.md) |
| UB / Bank 冲突 | [arch22](references/common/arch22/ub_bank_conflict.md) · [arch35](references/common/arch35/ub_resident_design.md) |
| 尾块处理 | [arch35 Tail Block](references/common/arch35/tail_block_design.md) |
| Cube-Vector 融合 | [arch35 CV 融合](references/common/arch35/cv_fusion_design.md) |
| 数据依赖写 / 重复目标归约 | [indexed write reduction](references/common/indexed_write_reduction.md) |
| Reg VF 编译与兼容 | [CANN / Reg VF FAQ](references/common/arch35/regbase/cann_version_compat_faq.md) |
| CANNBot-DSL 公共知识 | [cannbotdsl](references/common/arch35/cannbotdsl/index.md) |
| 模板与构建 | [template_usage](references/common/template_usage.md) |

## 使用规则

1. 先按**算子族**选入口，再按**目标代际**进入 `arch22/` 或 `arch35/`，不要跨代际套用结论。
2. 未收录的算子族返回「该算子族优化知识暂未收录」，不要编造优化经验。
3. 融合算子按内部计算单元拆解，每个内嵌 MatMul 单元独立命中 MatMul 族。
4. 扩展新算子族见 [`SKILL.md`](SKILL.md) 的「扩展新算子族」一节。
