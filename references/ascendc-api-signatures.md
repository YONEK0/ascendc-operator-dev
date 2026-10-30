# Ascend C 核心矢量 API 真实签名与契约速查表 (CANN 8.0 / 9.0+)

> **定位**：本表基于昇腾官方 CANN 8.0/9.0+ 实机头文件与 CANNBot 生产实践提炼，收录**最高频的 25 个核心矢量/搬运 API 的精确签名与避坑用法**。
> **目的**：AI 编写核函数时直接以此为 Ground Truth，**严禁凭空盲猜参数个数或去远端打探针测试**。

---

## 一、 核心矢量算术运算 (Vector Compute)

### 1. 符号函数 `Sign`
- **签名**：
  ```cpp
  template <typename T, bool isReuseSource = false>
  __aicore__ inline void Sign(const LocalTensor<T>& dstTensor, const LocalTensor<T>& srcTensor, const uint32_t calCount);
  ```
- **语义**：逐元素符号函数，**内置满足 `sign(0.0) = 0.0`**，`sign(x>0) = 1.0`，`sign(x<0) = -1.0`。
- **注意**：三参数版本为 CANN 8/9 原生推荐，**无需额外传 `sharedTmpBuffer`**。

### 2. 幂运算 `Power`
- **签名**：
  ```cpp
  // Tensor ^ 标量
  template <typename T>
  __aicore__ inline void Power(const LocalTensor<T>& dstTensor, const LocalTensor<T>& src0Tensor, const T& src1Scalar, const uint32_t calCount);
  
  // 标量 ^ Tensor
  template <typename T>
  __aicore__ inline void Power(const LocalTensor<T>& dstTensor, const T& src0Scalar, const LocalTensor<T>& src1Tensor, const uint32_t calCount);
  
  // Tensor ^ Tensor
  template <typename T>
  __aicore__ inline void Power(const LocalTensor<T>& dstTensor, const LocalTensor<T>& src0Tensor, const LocalTensor<T>& src1Tensor, const uint32_t calCount);
  ```
- **语义**：直接在 AI Core 矢量硬件流水上计算 $x^y$。
- **避坑**：核内**严禁调用 Host 的 `std::pow`**，标量求幂可借 8 元素 UB 缓冲区通过 `Power` 矢量完成。

### 3. 绝对值 `Abs`
- **签名**：
  ```cpp
  template <typename T>
  __aicore__ inline void Abs(const LocalTensor<T>& dstTensor, const LocalTensor<T>& srcTensor, const uint32_t calCount);
  ```

### 4. 标量乘法与加法 (`Muls`, `Adds`)
- **签名**：
  ```cpp
  template <typename T, bool isSetMask = true>
  __aicore__ inline void Muls(const LocalTensor<T>& dst, const LocalTensor<T>& src, const T& scalarValue, const int32_t& count);

  template <typename T, bool isSetMask = true>
  __aicore__ inline void Adds(const LocalTensor<T>& dst, const LocalTensor<T>& src, const T& scalarValue, const int32_t& count);
  ```
- **核心优化**：
  - `Muls(dst, src, 1.0f / c, count)` 代替广播除法，性能提升 5~10 倍；
  - `Adds(dst, src, -bias, count)` 代替广播减法。

### 5. 基础双目矢量运算 (`Add`, `Sub`, `Mul`, `Div`)
- **签名**：
  ```cpp
  template <typename T>
  __aicore__ inline void Add(const LocalTensor<T>& dst, const LocalTensor<T>& src0, const LocalTensor<T>& src1, uint32_t count);

  template <typename T>
  __aicore__ inline void Sub(const LocalTensor<T>& dst, const LocalTensor<T>& src0, const LocalTensor<T>& src1, uint32_t count);

  template <typename T>
  __aicore__ inline void Mul(const LocalTensor<T>& dst, const LocalTensor<T>& src0, const LocalTensor<T>& src1, uint32_t count);

  template <typename T>
  __aicore__ inline void Div(const LocalTensor<T>& dst, const LocalTensor<T>& src0, const LocalTensor<T>& src1, uint32_t count);
  ```
- **别名规则**：`dst` 允许与 `src0` 或 `src1` 指向同一个 LocalTensor（支持 In-Place 原地运算）。

### 6. 矢量常数填充 `Duplicate`
- **签名**：
  ```cpp
  template <typename T>
  __aicore__ inline void Duplicate(const LocalTensor<T>& dst, const T& scalarValue, const uint32_t count);
  ```

---

## 二、 精度转换 (`Cast`)

- **签名**：
  ```cpp
  template <typename DstT, typename SrcT>
  __aicore__ inline void Cast(const LocalTensor<DstT>& dst, const LocalTensor<SrcT>& src, const RoundMode roundMode, const uint32_t count);
  ```
- **RoundMode 铁律**：
  | 转换类型 | RoundMode | 含义 |
  |---|---|---|
  | `half` → `float` (升精度) | `RoundMode::CAST_NONE` | 零损失无条件扩展 |
  | `float` → `half` (降精度) | `RoundMode::CAST_ROUND` | 严格四舍五入，满足 IEEE 754 精度 |

---

## 三、 数据搬运与对齐 (`DataCopyPad`)

**铁律：所有 GM ↔ UB 搬运统一使用 `DataCopyPad` 的 Ext 参数重载，彻底杜绝越界和非对齐错误。**

- **参数结构体声明**：
  ```cpp
  // 1. 搬运参数 (统一使用 Ext)
  AscendC::DataCopyExtParams copyParams;
  copyParams.blockCount = 1;                              // 搬运块数 (连续行设为1)
  copyParams.blockLen   = byteLen;                        // 实际有效字节数 (例如 M * sizeof(T))
  copyParams.srcStride  = 0;
  copyParams.dstStride  = 0;
  copyParams.rsv        = 0;

  // 2. Pad 填充参数 (统一使用 Ext<T>)
  AscendC::DataCopyPadExtParams<T> padParams;
  padParams.isPad        = true;                         // 开启自动 32B 填充
  padParams.leftPadding  = 0;
  padParams.rightPadding = 0;                            // 尾部自动补零到 32B 边界
  padParams.paddingValue = static_cast<T>(0);
  ```

- **GM → UB (CopyIn)**：
  ```cpp
  AscendC::DataCopyPad(dstLocal, srcGm[offset], copyParams, padParams);
  AscendC::PipeBarrier<PIPE_ALL>();
  ```

- **UB → GM (CopyOut)**：
  ```cpp
  // 自动丢弃 UB 尾部 dummy 填充，绝不会写穿 GM
  AscendC::DataCopyPad(dstGm[offset], srcLocal, copyParams);
  AscendC::PipeBarrier<PIPE_ALL>();
  ```

- **⛔ 禁用提醒**：
  - `DataCopy` 仅能在**绝对确保 32B 整数倍且起址对齐**时使用；
  - `DataCopy` **绝不能在 UB 和 UB 之间拷贝**（UB 内部转换只能用 `Adds(dst, src, 0)` 或 `Cast`）。

---

## 四、 零死锁缓冲区管理 (`TPipe` + `TBuf`)

- **声明与初始化**：
  ```cpp
  TPipe pipe;
  TBuf<TPosition::VECCALC> myBuf;
  pipe.InitBuffer(myBuf, sizeInBytes); // 在 Init() 阶段一次性分配
  ```
- **获取指针**：
  ```cpp
  LocalTensor<float> tensor = myBuf.Get<float>(); // 零开销，天然 32B 对齐
  ```
- **禁止项**：主循环内**严禁调用 `TQue::AllocTensor / FreeTensor`**（队列深度为 1 时极易死锁 300 秒）。

---

## 五、 核函数声明与 Host 调用规约

### 1. 设备侧核函数（必须显式标注 `__vector__`）
```cpp
template <typename T>
__global__ __vector__ void my_op_custom(
    GM_ADDR in0, GM_ADDR in1, GM_ADDR out,
    uint32_t P, uint32_t R, uint32_t M,
    int32_t dtype, int32_t p_mode,
    uint32_t total_rows, uint32_t blockDim)
{
    KernelOp<T> op;
    op.Init(...);
    op.Process();
}
```

### 2. 宿主侧分发（`run_kernel`）
```cpp
extern "C" void run_kernel(..., aclrtStream stream, ...) {
    // 1. 形状解析 (从 info.tensors[0].shape 提取)
    // 2. 算力核数分配 blockDim
    // 3. 模态判断 (如 p_mode) 在 Host 侧完成
    if (dtype == 1) {
        my_op_custom<half><<<blockDim, nullptr, stream>>>(...);
    } else {
        my_op_custom<float><<<blockDim, nullptr, stream>>>(...);
    }
}
```

