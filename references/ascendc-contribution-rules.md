# Ascend C 算子社区贡献规范

> 适用范围：准备向 CANN / ops-math 等仓库提交算子代码，或按社区风格整理自有算子工程。
> **以目标仓库当前的 `CONTRIBUTING.md`、代码规范和 CI 为准**；本文件是通用清单，不替代仓库规范。

## 1. 许可证头

### `.cpp` / `.h` 文件

```cpp
/**
 * This program is free software, you can redistribute it and/or modify it.
 * Copyright (c) 2025 Huawei Technologies Co., Ltd.
 * This file is a part of the CANN Open Software.
 * Licensed under CANN Open Software License Agreement Version 2.0 (the "License").
 * Please refer to the License for details. You may not use this file except in compliance with the License.
 * THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING
 * BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
 * See LICENSE in the root of the software repository for the full text of the License.
 */
```

### `.py` / `.sh` 文件

```text
# This program is free software, you can redistribute it and/or modify it.
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This file is a part of the CANN Open Software.
# Licensed under CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
```

规则：

- 不得删除、遮蔽或改写已有版权头。
- 年份、版权主体、仓库名以目标仓库当前规范为准；新增文件使用当前年份。
- 如果目标仓库已有不同的许可证头，遵循仓库规范，并在提交说明中注明差异。

## 2. 目录与文件结构

按目标仓库当前贡献模型执行；常见布局：

```text
<op_name>/
├── op_host/
│   ├── <op_name>_def.cpp        # 算子原型、DataTypeList、注册
│   ├── <op_name>_tiling.cpp     # Tiling、platform 校验、workspace
│   └── <op_name>_infershape.cpp # 需要 Shape 推导时保留
├── op_kernel/
│   ├── <op_name>.cpp            # Kernel 入口与实现
│   ├── <op_name>_tiling.h       # TilingData POD
│   └── tiling_key_<op_name>.h   # TilingKey 定义
├── op_graph/                    # InferShape / InferDataType（如需要）
├── op_api/                      # ACLNN 接口（可选/标准交付件）
├── tests/
│   ├── ut/                      # 单元测试
│   └── st/                      # 系统测试
├── CMakeLists.txt
└── README.md
```

要点：

- `def.cpp` 只注册算子**实际支持**的数据类型与格式，不要声明不支持的组合。
- 算子契约需要 Shape 推导时保留 `op_host/infershape.cpp`；不要为了减少文件数而删除。
- 不暴露 ACLNN 接口时，在 `op_host/CMakeLists.txt` 配置 `ACLNNType` 为 `aclnn_exclude`（以仓库当前写法为准）。
- 不要添加或保留贡献模型明确排除的 `op_graph/`、`config/` 等目录。
- 单元测试应覆盖 `op_host`、`op_kernel`、`op_api` 中存在的部分。
- 仓库要求时，在算子外层 `README.md` 增加 contribution 说明。

## 3. 注册与 Tiling 规则

- **禁止 `TILING_KEY_IS` 宏分支**：核函数入口使用模板参数 + `if constexpr`。
- **TilingKey 不绑定数据类型**：数据类型由 `_def.cpp` 的 `DataTypeList` 驱动；TilingKey 只编码调度模式。
- **TilingData 为纯 POD**：无成员函数、虚函数、指针、引用、模板类或 STL。
- **GM 偏移/总量/stride 用 `int64_t`**：多维连乘时第一个操作数显式转为 `(int64_t)`。
- **避免为每种 dtype 单独加 TilingKey**：能用 `T_DTYPE` 宏或等价机制区分时优先复用。
- **`GET_TPL_TILING_KEY()` 不用魔法数字**：使用命名 kernel 宏或仓库标准模板。

## 4. 代码风格

- 控制语句（`if` / `else` / `for` / `while`）必须带花括号，即使只有一行。
- 一行只声明或赋值一个变量。
- 编译期常量优先 `constexpr`；Host 侧优先 C++ 风格转换（`static_cast<uint64_t>(x)`），避免 C 风格强转。
- 指针在使用前判空；除数在除法前检查；`coreNum`、`ubSize` 等平台参数按类型校验。
- 失败路径先输出 ERROR 级日志，再返回/抛异常。
- 命名表达真实含义与单位：`blockIdx` 表示 `GetBlockIdx()`，不要叫 `coreNum`。
- 大函数尽量控制在约 50 行以内（可维护性建议，不是机械拆分理由）。
- 删除冗余转换、冗余计算、多余空行；缩进与周围代码一致。

## 5. 验证清单

提交前逐项确认：

- [ ] 编译通过（目标仓库的 build 命令）。
- [ ] 单元测试通过（`tests/ut`）。
- [ ] 系统测试通过（`tests/st`，含边界/异常输入）。
- [ ] 静态分析/代码检查通过。
- [ ] 算子验证命令通过（按仓库要求）。
- [ ] 参考输入输出比对通过（`mismatched=0` / `PASSED`）。
- [ ] 许可证头完整。
- [ ] 没有 `printf`、`std::cout`、`<iostream>`、`std::min/max` 等核内违规。
- [ ] 没有临时文件、`.orig`/`.bak`、调试开关、硬编码路径。
- [ ] 提交说明只包含一个逻辑变更；上游基线只读，实验分支短生命周期。
- [ ] 如做了性能优化，记录改动点、预期收益、实测收益、回归结果。

## 6. 参考实现

- CANN ops-math：<https://gitcode.com/cann/ops-math>
- 官方算子样例与贡献示例：以目标仓库当前 `README.md` / `CONTRIBUTING.md` 为准。

参考实现只用于比较目录布局、注册方式、Tiling 数据和接口设计；不要复制不相关的行为或不支持的类型/格式注册。
