#!/usr/bin/env bash
# ----------------------------------------------------------------------------------------------------------
# run.sh - 本机评测入口脚本（需本机已安装 CANN 并连接昇腾 NPU）
# 执行: bash run.sh npu  或  bash run.sh cpu
# ----------------------------------------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

MODE="${1:-npu}"
echo "=========================================================="
echo "🚀 开始执行自定义算子工程评测 (模式: ${MODE})"
echo "=========================================================="

: "${ASCEND_HOME_PATH:?Source your CANN set_env.sh first}"
BUILD_DIR="build-${MODE}"

# 1. 编译
echo "[1/3] 正在使用 CMake 构建自定义算子与测试套件..."
cmake -S . -B "${BUILD_DIR}" \
    -DCMAKE_ASC_RUN_MODE="${MODE}" \
    -DCMAKE_ASC_ARCHITECTURES="${NPU_ARCH:-dav-2201}"
cmake --build "${BUILD_DIR}" --parallel 4

# 2. 运行测试程序
echo "[2/3] 正在昇腾 NPU 上运行测试驱动..."
(cd "${BUILD_DIR}" && ./test_op)

echo "=========================================================="
echo "🎉 评测流程执行完毕"
echo "=========================================================="
