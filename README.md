# Ascend C 算子开发 Skill

一个面向昇腾 Ascend C 算子开发全流程的 Agent Skill：从工程形态判定、脚手架生成、Tiling 设计、Kernel 编码，到同步审计、崩溃调试、ST/白盒测试、性能优化与本地打包。

## 适用

- 昇腾 Ascend C 单文件核函数（`kernel.asc`）的开发、调试、性能优化与验证。
- 标准自定义算子工程（`op_host/`、`op_kernel/`、`op_graph/`、`op_api/`）的开发、Tiling、测试与打包。
- CANN 8.x / 9.x，910B / 910C / 950 等昇腾平台上的算子问题。
- 需要把算子规格、数学公式或参考代码落成可编译、可验证的 Ascend C 实现。

## 不适用

- CUDA / GPU、ROCm、CPU-only 算子开发（除非任务明确是迁移到 Ascend 的前置分析）。
- 非昇腾平台的性能调优。
- 纯 Python / Web / 后端业务代码。
- 没有 Ascend C / CANN 上下文、也不打算在昇腾上运行的通用 C++ 问题。

## 快速开始

1. 把本目录放到 Agent 的 skills 目录，或按对应平台的 Skill 加载方式安装。
2. 在算子工程根目录运行：

   ```bash
   python <skill-dir>/scripts/op_helper.py
   ```

   `op_helper.py` 会判定工程形态；检测到 `op_host/` 或 `op_kernel/` 时自动补齐 `CMakeLists.txt`、`run.sh`、`main_test.asc`、`harness/` 等脚手架。

3. 按 `SKILL.md` 的路由表加载当前阶段需要的 1~2 个专项技能，不要一次性全量读取 `references/`。
4. 在装有 CANN 的昇腾机器上编译与验证：

   ```bash
   bash run.sh          # 默认 npu 模式
   bash run.sh cpu      # 无 NPU 时做功能调试（前提是当前 CANN 支持 CPU 模式）
   ```

5. 打包：

   ```bash
   python harness/pack_submission.py          # 纯净提交包 submission.zip
   python harness/pack_submission.py --full   # 完整工程包
   ```

## 目录结构

```text
.
├── SKILL.md                     # 主入口：适用边界、双步骤工作流、路由表、避坑铁律、完成定义
├── README.md                    # 本文件
├── LICENSE                      # CANN Open Software License Agreement Version 2.0
├── NOTICE                       # 第三方版权与许可证说明
├── scripts/
│   └── op_helper.py             # 工程形态判定、脚手架补齐、静态自检
└── references/
    ├── ascendc-api-signatures.md        # 矢量 API 真实签名速查
    ├── ascendc-custom-op-rules.md       # 自定义算子工程规范与红线
    ├── error-codes.md                   # CANN 错误码与故障路由速查
    ├── ascendc-contribution-rules.md    # 社区贡献、许可证头与目录规范
    ├── prompt-templates.md              # 一次性生成 Prompt 模板（按需加载）
    ├── ascend-npu-migration/            # CUDA / CPU 算子迁移到 Ascend C
    ├── ascendc-api-best-practices/      # API 使用最佳实践
    ├── ascendc-crash-debug/             # 卡死/崩溃/内存错误调试
    ├── ascendc-direct-invoke-template/  # Kernel 直调工程模板
    ├── ascendc-performance-best-practices/ # 性能优化（含 INDEX.md）
    ├── ascendc-st-design/               # 系统测试用例设计
    ├── ascendc-sync-audit/              # 同步审计与防死锁
    ├── ascendc-tiling-design/           # Tiling / 多核切分 / UB 预算
    ├── ascendc-whitebox-design/         # 白盒测试用例生成
    ├── ops-design-paradigms/            # 算子算法与计算范式选型（含 INDEX.md）
    ├── ops-direct-invoke-flash/         # 单文件核函数标杆源码
    └── sampleproject/                   # 可运行的自定义算子工程模板
```

## 环境要求

- CANN 8.x / 9.x（具体 API 以当前安装版本为准）。
- 昇腾 910B / 910C / 950 等平台；本地真机验证需要 NPU。
- Python 3.8+；主流程 `op_helper.py` 仅使用标准库。
- 部分 ST/白盒脚本需要 `numpy`、`pandas`、`pyyaml`；按需安装即可，不影响主流程。
- 无 NPU 时可使用 `bash run.sh cpu` 做功能调试（取决于当前 CANN 是否支持 CPU 模式）。

## 设计原则

- **工程形态由程序判定**：`op_helper.py` 检测 `op_host/` / `op_kernel/`，不靠 AI 猜测。
- **按需加载**：`references/` 内容很多，必须按 `SKILL.md` 的路由表只加载当前需要的 1~2 个专项。
- **单一模板源**：脚手架模板集中在 `references/sampleproject/`，避免多份副本漂移。
- **先证瓶颈再优化**：性能优化必须先 profiling、先测 floor，再按 7 层顺序执行。
- **如实交付**：没有真机验证时明确写「未在真机验证」，不用静态检查冒充真机结论。

## 许可证

本 Skill 包含 Huawei Technologies Co., Ltd. 的 CANN 开源材料，按
CANN Open Software License Agreement Version 2.0 分发。完整协议见
[`LICENSE`](LICENSE)，第三方版权说明见 [`NOTICE`](NOTICE)。

使用、修改或分发前请阅读协议；协议允许为 Huawei AI Processor / Software
系统开发、修改和分发，但要求保留版权声明并随附协议副本。

## 说明

- 本 Skill 不绑定任何评测平台、服务器或固定 IP；运行环境由使用者自行确认。
- 生成结果需要在实际工程和目标硬件上验证，本 Skill 不替代工程判断。
