# CANN 错误码与故障路由速查

> 用途：拿到报错后先分诊，再进入对应子技能。
> 错误码的精确含义以**当前 CANN 版本**的官方文档为准；本文只做路由，不替代官方文档，也不假设某个固定平台的错误码表。

## 0. 先做 5 件事

1. **保存完整日志**：不要只截最后一行；保留从第一条 `ERROR`/`EXCEPTION` 开始的上下文。
2. **记录环境**：`npu-smi info`、`echo $ASCEND_HOME_PATH`、CANN 版本、驱动/固件版本、SoC 型号。
3. **打开详细日志**：按版本文档设置 `ASCEND_GLOBAL_LOG_LEVEL=1`；需要终端输出时再设 `ASCEND_SLOG_PRINT_TO_STDOUT=1`。
4. **定位第一条错误**：故障链通常从第一条 `ERROR` 开始，后面的报错可能是连锁反应。
5. **最小复现**：固定 device、进程、kernelName、时间戳、输入 shape/dtype/属性；能缩小就缩小。

## 1. 按前缀 / 关键字分诊

| 前缀 / 关键字 | 常见来源 | 首查 | 进入 |
|---|---|---|---|
| `EZ9999` | GE / 图执行 / 算子编译通用错误 | 完整日志第一条 ERROR；算子名、输入 shape/dtype；Host 侧校验 | [crash-debug](ascendc-crash-debug/SKILL.md) · [api-best-practices](ascendc-api-best-practices/SKILL.md) |
| `GE` | Graph Engine | 图构建、算子注册、InferShape / InferDataType、属性 | [custom-op-rules](ascendc-custom-op-rules.md) |
| `RTS` | Runtime | device / stream / event、内存分配、`npu-smi` | [crash-debug](ascendc-crash-debug/SKILL.md) |
| `HCCL` | 集合通信 | rank table、网络、`HCCL_*` 环境变量、单机/多机配置 | 官方 HCCL 文档 |
| `AI_CPU` | AI CPU 算子 | 自定义 AI CPU 实现、Host 侧代码、算子注册 | [crash-debug](ascendc-crash-debug/SKILL.md) |
| `FE` | Framework / ACL | ACL 初始化、模型加载、输入描述、context 配置 | [crash-debug](ascendc-crash-debug/SKILL.md) |
| `Driver` | 驱动 / 固件 | `npu-smi info`、dmesg、驱动与 CANN 版本匹配 | 官方驱动文档 |
| `AIC Error` / `AIV Error` / `EXCP DS` / `ERR_INFO` | Kernel 异常 | kernelName、core type、异常 PC、TilingKey；必要时反汇编 | [crash-debug](ascendc-crash-debug/SKILL.md) |
| `OOM` / `out of memory` | 内存 | workspace、UB/L1/L0 预算、`npu-smi` | [tiling-design](ascendc-tiling-design/SKILL.md) · [crash-debug](ascendc-crash-debug/SKILL.md) |
| `hang` / `timeout` / 300s | 同步 / 死锁 | Alloc/Free、EnQue/DeQue、CrossCore flag、PipeBarrier | [sync-audit](ascendc-sync-audit/SKILL.md) |
| `precision` / `mismatch` | 数值 / 精度 | dtype、累加模式、Cast RoundMode、NaN/Inf、fast/fallback | [st-design](ascendc-st-design/SKILL.md) · [api-best-practices](ascendc-api-best-practices/SKILL.md) |
| 编译器 error（bisheng / ccec） | 编译器 | 第一条 error、Host/Device 宏、核内 STL / 浮点库用法 | [api-best-practices](ascendc-api-best-practices/SKILL.md) |

## 2. 常见症状 → 首查

| 症状 | 首查 |
|---|---|
| 编译报 `candidate function not viable` / `__host__ function` | 核内是否调用了 `std::pow`/`std::isinf`/`std::isnan`/`powf` 等 Host 库 |
| 编译报 `kernel type is not marked` | 核函数是否显式标注 `__vector__` / `__cube__` |
| 编译报 `Cannot determine link language` | `find_package(ASC)` 是否在 `project(... LANGUAGES ASC CXX)` 之前 |
| 运行 300 秒卡死 | `TQue` 是否在循环内 Alloc 未 Free；中间暂存是否改用 `TBuf` |
| 多核结果错乱 / 偶发越界 | 多核是否按 32B 独占写入；尾块是否用 `DataCopyPad` |
| 单核正常、多核异常 | 核间切分边界、Cacheline 踩踏、CrossCore 同步 |
| 结果偶发不一致 | 内存踩踏、竞争、未初始化、状态复用 |
| 精度不达预期 | 累加 dtype、Cast RoundMode、NaN/Inf、fast/fallback 路径 |
| 性能不达预期 | 先 profiling，再按 [性能优化顺序](ascendc-performance-best-practices/SKILL.md#优化顺序先证瓶颈再动手) |

## 3. 常用工具

- `npu-smi info`：设备、显存、进程、健康状态。
- plog：CANN 运行日志；先用 `ascendc-crash-debug/scripts/parse_plog.py` 提取卡死/崩溃/硬件异常信号。
- `mssanitizer`：越界、踩踏、非对齐、泄漏；见 [crash-debug/memcheck](ascendc-crash-debug/references/memcheck/)。
- `npu-objdump-toolkit`：异常 PC 精确反汇编；见 [crash-debug](ascendc-crash-debug/SKILL.md)。
- `msprof` / Ascend Insight：性能 profiling；先确认热点与 floor。
- `ASCEND_GLOBAL_LOG_LEVEL` / `ASCEND_SLOG_PRINT_TO_STDOUT`：日志级别与终端输出（以当前版本文档为准）。

## 4. 不要做

- 不要只贴最后一行报错，或把多个故障的日志混在一起。
- 不要在未确认 CANN 版本 / SoC 型号时套用其他版本的错误码解释。
- 不要修改 `$ASCEND_HOME_PATH`、`$ASCEND_OPP_PATH` 或 SDK 安装目录。
- 不要把日志中的 token、密钥、业务数据原样提交到公开 issue。
- 不要用静态检查结论代替真机复现结论。
