# Harness 开发脚手架说明

本目录是自定义算子工程的**本地开发辅助与自动化脚手架**，用于解决以下痛点：

1. 工程没有给 `run.sh`，不知道怎么生成测试数据和验证正确性。
2. 提交前担心残留 `printf` 或非法语法导致编译报错。
3. 手动打包容易把本地 `.bin`、日志或临时脚本误打进提交包。

> ⚠️ **注意**：本 `harness/` 目录属于开发者辅助套件，在生成纯净提交包时会被**自动白名单过滤**，不会进入最终提交包。

---

## 🛠️ 工具清单

| 脚本文件 | 功能说明 | 使用命令 |
|---|---|---|
| `gen_golden.py` | 自动生成测试输入与 PyTorch / NumPy 标准真值（.bin） | `python harness/gen_golden.py --hin 4 --win 4` |
| `check_cleanliness.py` | 静态扫描 `op_host` 和 `op_kernel`，确保无调试代码 | `python harness/check_cleanliness.py` |
| `pack_submission.py` | 本地打包：默认生成纯净提交包，`--full` 生成完整工程包 | `python harness/pack_submission.py` |

---

## 🚀 极简开发工作流（换算子仅需 3 步）

### 第一步：修改数据契约与切分
1. 打开 `op_kernel/<op>_tiling.h`，定义新算子所需的 POD 结构体。
2. 打开 `op_host/<op>.cpp`，在 `TilingFunc` 中计算 `blockDim` 和切分参数并写入 `tilingData`。

### 第二步：编写 AI Core 核心算法
1. 打开 `op_kernel/<op>.cpp`，在 `Compute` 中实现新算子的向量计算逻辑。
2. 保持 32 字节对齐规则，不要添加任何 `printf`。

### 第三步：编译、真机测试与本地打包
在装有 CANN 与昇腾 NPU 的机器上，进入工程根目录执行：

```bash
bash run.sh          # 默认 npu 模式
bash run.sh cpu      # 无 NPU 时做功能调试（前提是当前 CANN 支持 CPU 模式）
```

确认终端输出 `mismatched=0` 与 `PASSED`。

测试通过后，在本地打包：

```bash
python harness/pack_submission.py            # 纯净提交包 submission.zip
python harness/pack_submission.py --full     # 完整工程包 project_full.zip（含 run.sh / main_test.asc / harness）
```

`pack_submission.py` 会自动完成：
1. 静态自检代码纯净度（可加 `--skip-check` 跳过）。
2. 默认只收录 `CMakeLists.txt`、`README.md`、`kernel.asc` 以及 `op_host/`、`op_kernel/` 下的核心源码。
3. 生成 zip 文件并打印收录清单。
