# Ascend C 标准自定义算子工程开发规范与红线指南

> **适用范围**：标准自定义算子工程（含 `op_host/`、`op_kernel/`、`op_graph/`、`op_api/`），特别适用于各类昇腾竞赛与工程交付。

---

## 一、标准工程目录结构与职责划分

标准自定义算子工程目录形态：

```
{op_name}/
├── CMakeLists.txt                # 算子顶层构建配置
├── op_host/                      # Host 侧实现
│   ├── {op_name}_def.cpp         # 算子定义（OpDef: Input/Output/Attr/AddConfig）
│   ├── {op_name}_infershape.cpp  # Shape 推导实现与 IMPL_OP_INFERSHAPE
│   ├── {op_name}_tiling.cpp      # Tiling 切分算法实现与 IMPL_OP_OPTILING
│   └── CMakeLists.txt
├── op_kernel/                    # Kernel 侧实现
│   ├── {op_name}.cpp             # Kernel 入口函数（模板函数 + if constexpr）
│   ├── {op_name}_tiling.h        # TilingData 结构体与 TilingKey 声明（POD 布局）
│   ├── {op_name}.h               # Kernel 计算核心类（Init/Process/CopyIn/Compute/CopyOut）
│   └── CMakeLists.txt
├── op_graph/                     # 图推断与 IR 适配（必需）
│   ├── {op_name}_proto.h         # REG_OP 算子原型注册
│   └── {op_name}_graph_infer.cpp # InferDataType 实现与 IMPL_OP(OpName).InferDataType
└── op_api/                       # ACLNN 动态库接口（可选/标准交付件）
    ├── aclnn_{op_name}.cpp/.h    # L2 API（对外暴露两段式调用）
    └── {op_name}.cpp/.h          # L0 API（底层执行器）
```

---

## 二、Host 侧核心规范与四大红线

### 1. HOST-1: InferDataType 必须位于 `op_graph/` 目录（严禁放 `op_host/`）
- **红线规则**：通过 `REG_OP` 注册的算子，`InferDataType` 的实现与注册必须独立放在 `op_graph/xxx_graph_infer.cpp` 中。
- **禁止形态**：严禁在 `op_host/xxx_infershape.cpp` 中通过链式调用注册，例如：
  ```cpp
  // ❌ 严禁在 op_host 目录链式注册 InferDataType（历史违规）
  IMPL_OP_INFERSHAPE(MyOp)
      .InferShape(InferShapeMyOp)
      .InferDataType(InferDataTypeMyOp);
  ```
- **正确写法**：
  ```cpp
  // op_graph/my_op_graph_infer.cpp
  #include "graph/operator_reg.h"
  namespace ge {
  static graphStatus InferDataTypeMyOp(InferDataTypeContext* context) {
      context->SetOutputDataType(0, context->GetInputDataType(0));
      return GRAPH_SUCCESS;
  }
  IMPL_OP(MyOp).InferDataType(InferDataTypeMyOp); // ✅ 独立合规注册
  }
  ```

### 2. HOST-3: Platform 硬件参数必须按类型精确校验（判空 + 零值拦截）
- **红线规则**：从 `context->GetPlatformInfo()` 获取的平台信息必须在使用前完成校验，防止除零或切分异常。
- **类型语义匹配要求**：
  - `platformInfo` 指针解引用前**必须判空**；
  - 有符号数（`coreNum / aicNum / aivNum`，类型为 `int64_t`）：必须用 `<= 0` 拦截并返回 `ge::GRAPH_FAILED`；
  - 无符号数（`ubSize / blockSize`，类型为 `uint64_t`）：必须用 `== 0` 拦截（**严禁写 `<= 0`**，无符号数恒非负，写 `<= 0` 属于语义错误）。
- **标准拦截代码**：
  ```cpp
  auto platformInfo = context->GetPlatformInfo();
  OP_CHECK_IF(platformInfo == nullptr, OP_LOGE(context, "platformInfo is nullptr"), return ge::GRAPH_FAILED);

  auto coreNum = platformInfo->GetCoreNumAiv(); // 有符号 int64_t
  OP_CHECK_IF(coreNum <= 0, OP_LOGE(context, "coreNum must be > 0, got %ld", coreNum), return ge::GRAPH_FAILED);

  uint64_t ubSize = platformInfo->GetUBSize();  // 无符号 uint64_t
  OP_CHECK_IF(ubSize == 0, OP_LOGE(context, "ubSize must be > 0"), return ge::GRAPH_FAILED);
  ```

### 3. HOST-4: Platform 参数必须在 Tiling 中直接获取，禁止在 TilingParse 中经 compileInfo 传递
- **红线规则**：`coreNum`, `ubSize`, `blockSize` 等硬件参数是运行时属性，必须在 `Tiling` 方法中通过 `context->GetPlatformInfo()` 直接读取。
- **禁止形态**：严禁在编译期的 `TilingParse` 中读取并写入 `compileInfo`，然后在 `Tiling` 中从 `compileInfo->ubSize` 读取。该做法易引发赋值时序错误（引用到 0 值）或 UT 单测漂移。

### 4. Workspace 内存大小分配规范
- 若算子内部计算或调用的 Ascend C API 需要临时 Global Memory 工作空间：
  ```cpp
  size_t usrWorkspaceSize = ...; // 算子自身所需的 GM 字节数
  size_t sysWorkspaceSize = platformInfo->GetLibApiWorkSpaceSize();
  size_t totalWorkspace = usrWorkspaceSize + sysWorkspaceSize;

  auto workspaceSizes = context->GetWorkspaceSizes(1);
  OP_CHECK_IF(workspaceSizes == nullptr, OP_LOGE(context, "workspaceSizes is null"), return ge::GRAPH_FAILED);
  workspaceSizes[0] = totalWorkspace; // 若无需求则设为 0
  ```

---

## 三、TilingData 结构体规范与 64 位防溢出契约

`op_kernel/{op_name}_tiling.h` 是 Host 与 Kernel 间传递参数的关键媒介：

### 1. 严格 POD 纯数据契约
- **文件位置**：必须放置在 `op_kernel/` 目录下（编译器在线编译要求）。
- **禁止项**：
  - ❌ 禁止成员函数（包括任何普通方法或带 `__aicore__` 修饰的方法）；
  - ❌ 禁止虚函数、虚继承；
  - ❌ 禁止指针、引用；
  - ❌ 禁止 STL 容器（`std::vector`, `std::string` 等）或模板类。
- **允许项**：
  - ✅ 基础数据类型（`int64_t`, `uint32_t`, `float`, `bool`）；
  - ✅ 定长原生数组（如 `int64_t shape[4]`）。

### 2. RED-9: GM 内存偏移与大小必须强制使用 `int64_t`
- **红线规则**：涉及 Global Memory（GM）内存偏移量、总元素量、stride 的变量，在 TilingData 结构体中必须声明为 `int64_t`。
- **防隐蔽溢出**：连续多维相乘时，**第一个操作数必须显式强转为 `(int64_t)`**，防止在右侧先以 32 位计算溢出后再赋值给 64 位变量。
  ```cpp
  // ❌ 隐蔽溢出：右侧 4 个 uint32_t 先乘，溢出后再提升为 int64_t
  int64_t offset = batchIdx * numHeads * seqLen * headDim;

  // ✅ 正确：首个操作数强转，触发 64 位乘法全流程
  int64_t offset = (int64_t)batchIdx * numHeads * seqLen * headDim;
  ```

### 3. TilingData 标准定义模板
```cpp
#ifndef OP_TILING_H
#define OP_TILING_H

#include <cstdint>

struct MyOpTilingData {
    int64_t totalLength = 0;   // 总元素数量（必须 int64_t）
    int64_t blockLength = 0;   // 单核处理元素数量
    int64_t tileLength = 0;    // 单次 UB 搬运元素数量
    int64_t tileNum = 0;       // 单核 UB 循环迭代次数
    int64_t tailLength = 0;    // 尾块元素数量
    uint32_t coreNum = 0;      // 实际使用核数
};

#endif // OP_TILING_H
```

---

## 四、Kernel 侧核心规范与避坑红线

### 1. KERNEL-7: 严禁在 Kernel 中使用 `TILING_KEY_IS` 宏
- **红线规则**：Kernel 入口函数（`op_kernel/{op_name}.cpp`）中严禁使用 `if (TILING_KEY_IS(1))` 硬编码分支。
- **官方推荐标准**：使用模板参数 + `if constexpr` 编译期消除分支：
  ```cpp
  #define TPL_MODE_FP32 0
  #define TPL_MODE_FP16 1

  template <uint32_t schMode>
  __global__ __aicore__ void my_op(
      GM_ADDR x, GM_ADDR y, GM_ADDR workspace, GM_ADDR tiling)
  {
      GET_TILING_DATA(tilingData, tiling);
      if constexpr (schMode == TPL_MODE_FP32) {
          MyOpKernel<float> op;
          op.Init(x, y, tilingData);
          op.Process();
      } else if constexpr (schMode == TPL_MODE_FP16) {
          MyOpKernel<half> op;
          op.Init(x, y, tilingData);
          op.Process();
      }
  }
  ```

### 2. KERNEL-6: TilingKey 声明禁止绑定运算数据类型
- **红线规则**：`ASCENDC_TPL_ARGS_DECL` 宏中严禁使用 `ASCENDC_TPL_DATATYPE_DECL` 声明 `fp16/fp32/bf16` 作为 TilingKey 枚举。
- **正确做法**：将 dtype 差异转为整型枚举（如 `schMode`，使用 `ASCENDC_TPL_UINT_DECL`），在 Host 侧统一决策；或者运算数据类型通过 `_def.cpp` 的 `DataTypeList` 驱动（生成编译宏 `-DDTYPE_X`）。

### 3. KERNEL-8: Kernel 入口文件严禁 `_apt` 后缀
- 命名必须规范：`{op_name}.cpp` 或 `{op_name}_arch22.cpp`，禁止命名为 `{op_name}_apt.cpp`。

### 4. KERNEL-2: AllocTensor 与 FreeTensor 必须路径完备配对
- 在任何分支、边界条件、提前 `return` 或 `break` 路径上，已经 `AllocTensor` 的局部张量**必须显式调用 `FreeTensor` 或 `EnQue`**。
- 若提前退出漏掉 `FreeTensor`，会导致队列槽位泄漏，后续核函数迭代在 `AllocTensor` 处永久挂起（Hang）。

### 5. KERNEL-11: 禁止使用全局屏障 `PipeBarrier<PIPE_ALL>`
- `PIPE_ALL` 性能开销极大（清空所有流水管道）。应根据实际流水依赖使用细粒度 Barrier（如 `PipeBarrier<PIPE_V>()`），或优先依赖队列的 `EnQue/DeQue` 隐式硬件同步。

### 6. 双缓冲索引循环下溢防御
- 双缓冲场景下常用 `(loop - 1) % N` 索引上一轮缓冲区。
- **严重陷阱**：当 `loop` 声明为 `uint32_t` 且 `loop = 0` 时，`loop - 1` 下溢为 `UINT32_MAX`（`4294967295`），直接导致越界访存或死机。
- **防范写法**：
  ```cpp
  if (loop == 0) {
      // 第 0 轮特殊初始化处理
  } else {
      uint32_t prevIdx = (loop - 1) % N; // loop >= 1，安全
  }
  ```

### 7. 数据搬运与对齐约束（DataCopyPad Ext 规范与 UB 32B 起始对齐）
- 统一使用 `DataCopyPad` 的 Ext 版本：
  ```cpp
  AscendC::DataCopyExtParams copyParams{1, actualBytes, 0, 0, 0};
  AscendC::DataCopyPadExtParams<T> padParams{false, 0, 0, 0};
  AscendC::DataCopyPad(dstLocal, srcGm, copyParams, padParams);
  ```
- **UB 首地址 32B 对齐红线**：虽然 `DataCopyPad` 允许数据长度非 32B 对齐，但 **UB 缓冲区的起始地址指针必须 32 字节对齐**。按行多行搬运时，每行在 UB 内的起始地址必须是 32 的倍数，否则触发硬件异常 `AIV error 80: UB address is not aligned`。

### 8. RED-10: SuperKernel / 图融合场景禁止裸指针解引用 GM
- 在图融合场景下，严禁写 `*(__gm__ float*)gmPtr` 直接读写 Global Memory。
- 必须通过 `GlobalTensor::GetValue(0)` / `SetValue(0, val)` 或调用 `DataCopyPad` 走标准硬件通路。

---

## 五、核函数类标准架构模式（CopyIn - Compute - CopyOut）

```cpp
template <typename T>
class KernelMyOp {
public:
    __aicore__ inline KernelMyOp() {}
    __aicore__ inline void Init(GM_ADDR x, GM_ADDR y, const MyOpTilingData& tilingData) {
        tiling_ = tilingData;
        int64_t coreOffset = tiling_.blockLength * AscendC::GetBlockIdx();
        xGm.SetGlobalBuffer((__gm__ T*)x + coreOffset, tiling_.blockLength);
        yGm.SetGlobalBuffer((__gm__ T*)y + coreOffset, tiling_.blockLength);

        pipe.InitBuffer(inQueueX, 2, tiling_.tileLength * sizeof(T));
        pipe.InitBuffer(outQueueY, 2, tiling_.tileLength * sizeof(T));
    }

    __aicore__ inline void Process() {
        for (int32_t i = 0; i < tiling_.tileNum; i++) {
            CopyIn(i);
            Compute(i);
            CopyOut(i);
        }
    }

private:
    __aicore__ inline void CopyIn(int32_t progress) {
        AscendC::LocalTensor<T> xLocal = inQueueX.AllocTensor<T>();
        int64_t offset = progress * tiling_.tileLength;
        AscendC::DataCopyExtParams copyParams{1, static_cast<uint32_t>(tiling_.tileLength * sizeof(T)), 0, 0, 0};
        AscendC::DataCopyPadExtParams<T> padParams{false, 0, 0, 0};
        AscendC::DataCopyPad(xLocal, xGm[offset], copyParams, padParams);
        inQueueX.EnQue(xLocal);
    }

    __aicore__ inline void Compute(int32_t progress) {
        AscendC::LocalTensor<T> xLocal = inQueueX.DeQue<T>();
        AscendC::LocalTensor<T> yLocal = outQueueY.AllocTensor<T>();

        // 纯向量计算，无 std:: 函数，连续 count 形态
        AscendC::Abs(yLocal, xLocal, tiling_.tileLength);

        outQueueY.EnQue(yLocal);
        inQueueX.FreeTensor(xLocal);
    }

    __aicore__ inline void CopyOut(int32_t progress) {
        AscendC::LocalTensor<T> yLocal = outQueueY.DeQue<T>();
        int64_t offset = progress * tiling_.tileLength;
        AscendC::DataCopyExtParams copyParams{1, static_cast<uint32_t>(tiling_.tileLength * sizeof(T)), 0, 0, 0};
        AscendC::DataCopyPad(yGm[offset], yLocal, copyParams);
        outQueueY.FreeTensor(yLocal);
    }

private:
    AscendC::TPipe pipe;
    AscendC::TQue<AscendC::TPosition::VECIN, 2> inQueueX;
    AscendC::TQue<AscendC::TPosition::VECOUT, 2> outQueueY;
    AscendC::GlobalTensor<T> xGm;
    AscendC::GlobalTensor<T> yGm;
    MyOpTilingData tiling_;
};
```

