---
name: ascend-npu-migration
description: 将 CUDA / CPU 算子逻辑迁移到昇腾 Ascend C / CANN 的迁移分析与改造技能。适用于把现有 CUDA kernel、PyTorch/NumPy 参考实现或 CPU 算子改写成 Ascend C 单文件核函数或标准自定义算子工程；不适用于纯 CUDA 性能调优或非昇腾平台迁移。
---

# CUDA / CPU 算子迁移到 Ascend C

本技能处理「已有实现 → Ascend C」的迁移，不负责从零设计新算子（那走 `ops-design-paradigms` 和 `ascendc-tiling-design`）。

## 适用边界

**适用**：

- 已有 CUDA kernel、PyTorch/NumPy 参考实现或 CPU 算子，需要落成 Ascend C。
- 需要先做迁移可行性分析、构造映射表、识别高风险 API。
- 需要把线程/共享内存/同步模型改写成 Ascend 的 block/UB/流水模型。

**不适用**：

- 纯 CUDA 性能调优、非昇腾平台迁移。
- 没有源实现、只有一句算子描述的从零设计（走范式选型 + Tiling 设计）。
- 框架级迁移（整模型/整训练流程），本技能只覆盖算子级。

## 迁移工作流

### 1. 盘点源实现

记录：

- 语言/框架：CUDA C++、PyTorch、NumPy、TVM、Triton 等。
- 算子语义：数学公式、边界条件、特殊值（NaN/Inf/0/负数）。
- 输入输出：shape、dtype、layout（NCHW/NHWC/ND）、stride、广播规则。
- 精度：累加 dtype、舍入模式、容差要求。
- 并行结构：grid/block/thread、warp、shared memory、同步点。
- 特殊构造：atomics、warp shuffle、动态并行、递归、函数指针、模板元编程。

### 2. 建立映射表

先产出「源构造 → Ascend 等价 → 风险 → 验证方式」四列表，再动代码。常见映射：

| 源构造（CUDA/CPU） | Ascend C 等价 | 风险 / 注意 |
|---|---|---|
| `grid` / `block` / `thread` | `blockDim` + Tiling 切分；block 内用 Vector/SIMT 处理数据 | Ascend 不是「一 thread 一元素」；按 tile 处理，注意尾块 |
| `blockIdx.x` / `threadIdx.x` | `GetBlockIdx()` + Tiling 偏移 | 多核按 32B 独占写入，避免 Cacheline 踩踏 |
| global memory | GM（Global Memory） | 用 `DataCopyPad` 处理非对齐；GM 偏移用 `int64_t` |
| shared memory | UB（Unified Buffer） | UB 容量有限（按目标平台预算）；中间暂存优先 `TBuf` |
| L1 / L0 cache（Cube） | L1 / L0A / L0B / L0C | 仅 Cube 路径；按 MatMul 族指南规划 |
| `__syncthreads()` | `EnQue/DeQue`、`SetFlag/WaitFlag`、`SyncAll` | 按流水类型选择；禁止 `PipeBarrier<PIPE_ALL>` 粗粒度屏障 |
| warp shuffle | Reg / SIMT 跨 lane 操作或重排到 UB | 先确认目标架构是否支持；不支持时改数据布局 |
| atomicAdd 等 | `AscendC::AtomicAdd` 等原子 API | 确认 dtype/对齐/目标平台支持；注意确定性 |
| `__shared__` 常量表 | GM 常量 + `DataCopy` 到 UB | 常量表放 GM，按需搬入；不要放核内大数组 |
| `printf` / `std::cout` | 删除；用 `DumpTensor`/`PRINTF` 仅限调试 | 生产代码禁止调试打印 |
| `std::pow` / `isinf` / `isnan` | Host 侧预计算 + `int32_t` 模式下发；核内用 `AscendC::Power` | 核内不能链接 Host STL/libm |
| 递归 / 动态并行 / 函数指针 | 改写为迭代/静态分支/模板 | Ascend kernel 不支持这些构造 |
| FP16 累加 | 中间用 FP32，最后 `Cast(..., CAST_ROUND)` 回 FP16 | 避免溢出与累积误差 |
| 非对齐尾块 | `DataCopyPad` + `DataCopyExtParams` | 裸 `DataCopy` 可能越界/踩踏 |

> 上表是迁移起点，不是 API 保证；具体签名、约束和目标平台支持以 `ascendc-api-signatures.md` 与当前 CANN 文档为准。

### 3. 选择落地形态

- **单文件核函数（`kernel.asc`）**：源实现是单个 elementwise/reduction kernel，逻辑独立；走 `ops-direct-invoke-flash`。
- **标准自定义算子工程**：需要 op_host/op_kernel/op_graph/op_api、Tiling、Shape 推导、测试；走 `op_helper.py` + `ascendc-custom-op-rules.md`。

### 4. 改写并行与内存模型

1. 把源并行结构映射为 `blockDim` + Tiling：先按总数据量/UB 预算算 tile，再分核。
2. 多核切分以 32B 为最小粒度；每核写自己的独占区间。
3. 非对齐读写统一 `DataCopyPad`；UB 起始地址 32B 对齐。
4. 用 `TPipe` + `TBuf` 管理中间缓冲；不要在循环内反复 Alloc/Free。
5. 同步按流水类型插入；避免全局粗粒度屏障。

### 5. 改写数学与精度

- 核内禁止 Host STL/libm；浮点分支在 Host 侧算好，以标量下发。
- FP16 输入在 FP32 下计算，最后 Cast 回 FP16。
- 记录精度口径：ULP、相对/绝对误差、NaN/Inf 行为、fast/fallback 一致性。
- 对特殊值（0、负数、NaN、Inf、次正规数）单独设计用例。

### 6. 验证

1. **黄金参考**：用 PyTorch/NumPy/CPU 版本生成输入与期望输出。
2. **单元/系统测试**：走 `ascendc-st-design` / `ascendc-whitebox-design`。
3. **真机**：`bash run.sh`，确认 `mismatched=0` / `PASSED`。
4. **数值对比**：按约定的 ULP/相对误差比较；不要只看「看起来差不多」。
5. **性能**：先 profiling，再按 `ascendc-performance-best-practices` 的 7 层顺序优化。

### 7. 输出迁移报告

建议格式：

```markdown
## 迁移计划

| 源构造 | Ascend 等价 | 风险 | 验证 |
|---|---|---|---|
| ... | ... | ... | ... |

## 未映射项

- <构造>：为什么无法映射；替代方案；是否需要改算法

## 风险清单

- 精度风险：...
- 同步风险：...
- 性能风险：...
- 平台限制：...

## 验证结果

- 黄金参考：...
- 单测/ST：...
- 真机：mismatched=0 / PASSED / 未验证（原因）
```

## 常见迁移陷阱

- **把 CUDA 线程模型直接照搬**：Ascend 不是一 thread 一元素；先 tile 化。
- **shared memory 当无限容量**：UB 有预算，先算容量再切 tile。
- **`__syncthreads()` 直接换成 `SyncAll`**：先确认是核内流水同步还是核间同步；用错会死锁或读到半成品。
- **忽略 32B 对齐**：非对齐尾块必须 `DataCopyPad`；多核边界按 32B 独占。
- **在核内用 `std::pow`/`isinf`/`isnan`**：编译期报 `__host__ function`；Host 侧预计算。
- **FP16 全程累加**：精度/溢出风险；中间升 FP32。
- **只跑一个 shape**：迁移验证要覆盖尾块、非整除、空 tensor、极端值。
- **没有真机就说通过**：按 DoD 写「未在真机验证」。

## 相关技能

- 工程脚手架：`op_helper.py`、`references/sampleproject/`
- 算子规范：`references/ascendc-custom-op-rules.md`
- 范式选型：`references/ops-design-paradigms/SKILL.md`
- Tiling：`references/ascendc-tiling-design/SKILL.md`
- 测试：`references/ascendc-st-design/SKILL.md`、`references/ascendc-whitebox-design/SKILL.md`
- 性能：`references/ascendc-performance-best-practices/SKILL.md`
- 调试：`references/ascendc-crash-debug/SKILL.md`、`references/ascendc-sync-audit/SKILL.md`
