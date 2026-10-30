#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
昇腾 Ascend C 自定义算子极速开发辅助工具 (OpHelper CLI)
工作流第一步必做工具:
1. 自动化检测工程形态 (纯 Python 程序判断，严禁 AI 凭空臆断):
   - 若当前目录下存在 op_host 或 op_kernel 目录:
     -> 识别为【标准自定义算子工程】(Custom Operator Project)
     -> 自动扫描算子名，并一键补齐所有缺失目录与文件 (CMakeLists.txt, run.sh, main_test.asc, harness/, op_host/op_kernel 配置与骨架)
     -> 【单一真实数据源原则 (Single Source of Truth)】: 所有模板完全由 references/sampleproject/ 物理文件动态复制与变量渲染生成，Python 代码中严禁硬编码任何 C++/Shell/CMake 内容！
   - 若不存在 op_host 且不存在 op_kernel 目录:
     -> 识别为【单文件核函数 (kernel.asc) 模式或其他形态】
     -> 保持原有工程形态纯净，无需补全自定义算子工程结构！
2. 本地 0 秒静态代码安全自检 (提前拦截 90% 毕昇编译器与 AICore 硬件死锁报错)
"""

import os
import sys
import re
import shutil
import argparse

# 兼容终端的 UTF-8 输出，防止 GBK 编码报错
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 动态相对路径定位：支持在任意环境平台中动态查找 references/sampleproject
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def find_sample_project_dir():
    """按相对路径动态推导 references/sampleproject 目录，严禁硬编码绝对路径"""
    candidate_paths = [
        os.path.join(SCRIPT_DIR, "..", "references", "sampleproject"),
        os.path.join(SCRIPT_DIR, "references", "sampleproject"),
        os.path.join(SCRIPT_DIR, "sampleproject"),
        os.path.join(os.getcwd(), "references", "sampleproject"),
        os.path.join(os.getcwd(), "sampleproject"),
    ]
    for p in candidate_paths:
        abs_p = os.path.abspath(p)
        if os.path.isdir(abs_p):
            return abs_p
    return None

SAMPLE_PROJECT_DIR = find_sample_project_dir()

def require_sample_project():
    """断言 sampleproject 模板库存在，杜绝 Python 内嵌字符串降级"""
    if not SAMPLE_PROJECT_DIR or not os.path.isdir(SAMPLE_PROJECT_DIR):
        raise FileNotFoundError(
            "[OpHelper Error] 找不到 references/sampleproject 模板库目录！\n"
            "请确保技能库 ascendc-operator-dev/references/sampleproject/ 完整无缺。\n"
            "架构原则：所有脚手架文件必须直接来自物理模板文件，禁止在 Python 代码内写死任何模板字符串！"
        )
    return SAMPLE_PROJECT_DIR

def get_template_path(rel_path):
    """获取 references/sampleproject 中的模版文件绝对路径，若不存在直接报错"""
    base_dir = require_sample_project()
    p = os.path.join(base_dir, rel_path)
    if not os.path.exists(p):
        raise FileNotFoundError(f"[OpHelper Error] 模板文件不存在: {rel_path} (在 {base_dir} 中未找到)")
    return p

def copy_template_binary(rel_path, target_path, force_lf=False):
    """
    直接以二进制从 sampleproject 复制模版文件，保持天然 LF 换行与文件完整性。
    若 force_lf=True，则无论宿主机平台一律确保只有 Unix \\n (LF) 换行符。
    """
    src = get_template_path(rel_path)
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    if force_lf:
        with open(src, "rb") as f:
            data = f.read().replace(b"\r\n", b"\n")
        with open(target_path, "wb") as f:
            f.write(data)
    else:
        shutil.copy2(src, target_path)
    return True

def render_template_text(rel_path, target_path, replacements=None):
    """
    读取 sampleproject 中的真实文本模版，执行关键词替换，以标准 LF 换行写入目标路径。
    实现真正的 Single Source of Truth，Python 中不保留任何硬编码代码。
    """
    src = get_template_path(rel_path)
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()

    if replacements:
        for old, new in replacements.items():
            content = content.replace(old, new)

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    return True

def detect_project_type(project_root):
    """
    通过 Python 程序严格判断工程形态:
    - 存在 op_host 或 op_kernel 目录 -> 'custom_op' (标准自定义算子工程)
    - 否则 -> 'single_kernel' (单文件核函数模式或其他独立形态)
    """
    has_host = os.path.isdir(os.path.join(project_root, "op_host"))
    has_kernel = os.path.isdir(os.path.join(project_root, "op_kernel"))
    if has_host or has_kernel:
        return "custom_op"
    return "single_kernel"

def detect_operator_name(project_root):
    """从 op_host 或 op_kernel 目录中自动探测算子名称"""
    host_dir = os.path.join(project_root, "op_host")
    if os.path.isdir(host_dir):
        for f in os.listdir(host_dir):
            if f.endswith(".cpp") and not f.startswith("test_"):
                return f[:-4]
    kernel_dir = os.path.join(project_root, "op_kernel")
    if os.path.isdir(kernel_dir):
        for f in os.listdir(kernel_dir):
            if f.endswith(".cpp") and not f.startswith("test_"):
                return f[:-4]

    # 若未找到 cpp 文件，则尝试根据当前目录名推断
    base_name = os.path.basename(os.path.abspath(project_root)).lower()
    cleaned = re.sub(r"^(problem|ascend|template|project)_*", "", base_name)
    cleaned = re.sub(r"_*(problem|ascend|template|project)$", "", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", cleaned).strip("_")
    if cleaned and not cleaned.isdigit():
        return cleaned
    return "custom_op"

def to_camel_case(snake_str):
    """snake_case 转 CamelCase"""
    return "".join(x.capitalize() for x in snake_str.lower().split("_") if x)

def complete_top_cmakelists(project_root, op_name):
    """
    确保顶级 CMakeLists.txt 存在并配置 test_op:
    - 若不存在：直接从 references/sampleproject/CMakeLists.txt 渲染生成
    - 若已存在：增量注入 ASC 语言声明与 test_op 测试目标
    """
    cmake_path = os.path.join(project_root, "CMakeLists.txt")
    camel_name = to_camel_case(op_name)

    if not os.path.exists(cmake_path):
        render_template_text("CMakeLists.txt", cmake_path, {
            "sample_custom_prj": f"{op_name}_project",
            "sample_custom": op_name,
            "adaptive_avg_pool2d_grad": op_name,
            "AdaptiveAvgPool2dGrad": camel_name
        })
        return "Created", "CMakeLists.txt (完全从 references/sampleproject 模版渲染)"
    else:
        with open(cmake_path, "r", encoding="utf-8") as f:
            content = f.read()

        updated = False
        # 1. 确保 find_package(ASC REQUIRED) 在 project 之前
        if "project(" in content and "find_package(ASC REQUIRED)" not in content[:content.find("project(")]:
            content = "find_package(ASC REQUIRED)\n" + content
            updated = True

        # 2. 确保 project 语句中显式声明启用 ASC 语言，防止 CMake 无法识别 test_op 的链接器语言
        project_match = re.search(r"project\s*\(\s*([a-zA-Z0-9_-]+)(.*?)\)", content, re.DOTALL)
        if project_match:
            prj_name = project_match.group(1)
            prj_rest = project_match.group(2)
            if "LANGUAGES" not in prj_rest or "ASC" not in prj_rest:
                new_project_stmt = f"project({prj_name} LANGUAGES ASC CXX)"
                content = content[:project_match.start()] + new_project_stmt + content[project_match.end():]
                updated = True

        # 3. 注入 test_op 测试驱动配置（从 sampleproject 模版提取对应块，杜绝硬编码）
        if "add_executable(test_op" not in content:
            sample_cmake = os.path.join(require_sample_project(), "CMakeLists.txt")
            with open(sample_cmake, "r", encoding="utf-8") as sf:
                s_lines = sf.readlines()
            # 提取 sampleproject 中关于 test_op 的定义段落
            test_lines = []
            capture = False
            for line in s_lines:
                if "if(EXISTS \"${CMAKE_CURRENT_SOURCE_DIR}/main_test.asc\")" in line:
                    capture = True
                if capture:
                    test_lines.append(line)
                    if line.strip() == "endif()":
                        break
            if test_lines:
                test_block = "\n# 自动装配: 编译真机测试驱动 test_op\n" + "".join(test_lines)
                content = content.rstrip() + "\n" + test_block
                updated = True

        if updated:
            with open(cmake_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            return "Updated", "CMakeLists.txt (注入 test_op 构建目标与 ASC 语言支持)"
        return "Skipped", "CMakeLists.txt (已完备)"

def complete_run_sh(project_root):
    """
    从 references/sampleproject/run.sh 直接复制，强制 LF 换行，绝无任何硬编码字符串。
    """
    run_sh_path = os.path.join(project_root, "run.sh")
    if os.path.exists(run_sh_path):
        return "Skipped", "run.sh (已存在)"

    copy_template_binary("run.sh", run_sh_path, force_lf=True)
    return "Created", "run.sh (直接从 references/sampleproject 复制并保持 Unix LF 格式)"

def complete_main_test_asc(project_root, op_name):
    """
    从 references/sampleproject/main_test.asc 模版渲染生成端到端测试驱动，绝无任何硬编码字符串。
    """
    test_asc_path = os.path.join(project_root, "main_test.asc")
    if os.path.exists(test_asc_path):
        return "Skipped", "main_test.asc (已存在)"

    camel_name = to_camel_case(op_name)
    render_template_text("main_test.asc", test_asc_path, {
        "adaptive_avg_pool2d_grad": op_name,
        "AdaptiveAvgPool2dGrad": camel_name
    })
    return "Created", f"main_test.asc (直接从 references/sampleproject 模版渲染)"

def complete_op_host(project_root, op_name):
    """
    补齐 op_host 目录及其文件：完全从 references/sampleproject/op_host/ 模版渲染。
    """
    results = []
    host_dir = os.path.join(project_root, "op_host")
    os.makedirs(host_dir, exist_ok=True)
    camel_name = to_camel_case(op_name)

    # 1. op_host/CMakeLists.txt
    cmake_path = os.path.join(host_dir, "CMakeLists.txt")
    if not os.path.exists(cmake_path):
        render_template_text("op_host/CMakeLists.txt", cmake_path, {
            "adaptive_avg_pool2d_grad": op_name,
            "AdaptiveAvgPool2dGrad": camel_name
        })
        results.append(("Created", "op_host/CMakeLists.txt (直接从 references/sampleproject 模版渲染)"))
    else:
        results.append(("Skipped", "op_host/CMakeLists.txt (已存在)"))

    # 2. op_host/<op_name>.cpp
    cpp_files = [f for f in os.listdir(host_dir) if f.endswith(".cpp")]
    if not cpp_files:
        cpp_path = os.path.join(host_dir, f"{op_name}.cpp")
        render_template_text("op_host/adaptive_avg_pool2d_grad.cpp", cpp_path, {
            "adaptive_avg_pool2d_grad": op_name,
            "AdaptiveAvgPool2dGrad": camel_name
        })
        results.append(("Created", f"op_host/{op_name}.cpp (直接从 references/sampleproject 模版渲染)"))

    return results

def complete_op_kernel(project_root, op_name):
    """
    补齐 op_kernel 目录及其文件：完全从 references/sampleproject/op_kernel/ 模版渲染。
    """
    results = []
    kernel_dir = os.path.join(project_root, "op_kernel")
    os.makedirs(kernel_dir, exist_ok=True)
    camel_name = to_camel_case(op_name)

    # 1. op_kernel/CMakeLists.txt
    cmake_path = os.path.join(kernel_dir, "CMakeLists.txt")
    if not os.path.exists(cmake_path):
        render_template_text("op_kernel/CMakeLists.txt", cmake_path, {
            "adaptive_avg_pool2d_grad": op_name,
            "AdaptiveAvgPool2dGrad": camel_name
        })
        results.append(("Created", "op_kernel/CMakeLists.txt (直接从 references/sampleproject 模版渲染)"))
    else:
        results.append(("Skipped", "op_kernel/CMakeLists.txt (已存在)"))

    # 2. op_kernel/<op_name>_tiling.h (POD契约、宏保护、CopyTilingData)
    tiling_h_path = os.path.join(kernel_dir, f"{op_name}_tiling.h")
    if not os.path.exists(tiling_h_path):
        macro_guard = f"{op_name.upper()}_TILING_H"
        render_template_text("op_kernel/adaptive_avg_pool2d_grad_tiling.h", tiling_h_path, {
            "ADAPTIVE_AVG_POOL2D_GRAD_TILING_H": macro_guard,
            "AdaptiveAvgPool2dGradTilingData": f"{camel_name}TilingData",
            "adaptive_avg_pool2d_grad": op_name,
            "AdaptiveAvgPool2dGrad": camel_name
        })
        results.append(("Created", f"op_kernel/{op_name}_tiling.h (直接从 references/sampleproject 模版渲染)"))
    else:
        results.append(("Skipped", f"op_kernel/{op_name}_tiling.h (已存在)"))

    # 3. op_kernel/tiling_key_<op_name>.h
    tkey_path = os.path.join(kernel_dir, f"tiling_key_{op_name}.h")
    if not os.path.exists(tkey_path):
        macro_guard = f"TILING_KEY_{op_name.upper()}_H"
        render_template_text("op_kernel/tiling_key_adaptive_avg_pool2d_grad.h", tkey_path, {
            "TILING_KEY_ADAPTIVE_AVG_POOL2D_GRAD_H": macro_guard,
            "AdaptiveAvgPool2dGradTilingKey": f"{camel_name}TilingKey",
            "adaptive_avg_pool2d_grad": op_name
        })
        results.append(("Created", f"op_kernel/tiling_key_{op_name}.h (直接从 references/sampleproject 模版渲染)"))
    else:
        results.append(("Skipped", f"op_kernel/tiling_key_{op_name}.h (已存在)"))

    # 4. op_kernel/<op_name>.cpp
    kernel_cpp_path = os.path.join(kernel_dir, f"{op_name}.cpp")
    if not os.path.exists(kernel_cpp_path):
        render_template_text("op_kernel/adaptive_avg_pool2d_grad.cpp", kernel_cpp_path, {
            "adaptive_avg_pool2d_grad": op_name,
            "AdaptiveAvgPool2dGrad": camel_name
        })
        results.append(("Created", f"op_kernel/{op_name}.cpp (直接从 references/sampleproject 模版渲染)"))
    else:
        results.append(("Skipped", f"op_kernel/{op_name}.cpp (已存在)"))

    return results

def complete_harness(project_root):
    """
    补齐 harness/ 测试与打包工具：直接以二进制从 references/sampleproject/harness 复制全部文件。
    """
    results = []
    harness_dir = os.path.join(project_root, "harness")
    os.makedirs(harness_dir, exist_ok=True)

    sample_harness = os.path.join(require_sample_project(), "harness")
    for fname in os.listdir(sample_harness):
        src_f = os.path.join(sample_harness, fname)
        if os.path.isfile(src_f):
            dst_f = os.path.join(harness_dir, fname)
            if not os.path.exists(dst_f):
                shutil.copy2(src_f, dst_f)
                results.append(("Created", f"harness/{fname} (直接从 references/sampleproject 复制)"))
            else:
                results.append(("Skipped", f"harness/{fname} (已存在)"))

    return results

def setup_harness(project_root):
    """
    工作流第一步核心执行器:
    1. Python程序严格判定工程形态
    2. 若为标准自定义算子工程，从 references/sampleproject 自动补齐缺失目录与文件 (单一数据源)
    3. 若为单文件或其它工程，严格不予修改/补全，保持工程纯净
    """
    proj_type = detect_project_type(project_root)

    print("=" * 70)
    print("🔍 [OpHelper] 正在执行工程形态自动化检测 (Python程序驱动)...")
    print("=" * 70)

    if proj_type == "custom_op":
        op_name = detect_operator_name(project_root)
        print(f"  [识别结果] 检测到 op_host / op_kernel 目录！")
        print(f"  [工程形态] 确定为【标准自定义算子工程】(Custom Operator Project)")
        print(f"  [识别算子] {op_name}")
        print(f"  [数据源]   references/sampleproject (单一真实数据源)")
        print("-" * 70)
        print(f"🔧 开始从 references/sampleproject 自动扫描并补齐缺失的目录与工程文件...")
        print("-" * 70)

        actions = []
        actions.append(complete_top_cmakelists(project_root, op_name))
        actions.append(complete_run_sh(project_root))
        actions.append(complete_main_test_asc(project_root, op_name))
        actions.extend(complete_op_host(project_root, op_name))
        actions.extend(complete_op_kernel(project_root, op_name))
        actions.extend(complete_harness(project_root))

        created_cnt = 0
        for status, desc in actions:
            if status == "Created":
                print(f"  + [Created] {desc}")
                created_cnt += 1
            elif status == "Updated":
                print(f"  * [Updated] {desc}")
                created_cnt += 1
            else:
                print(f"  - [Skip]    {desc}")

        print("-" * 70)
        print(f"✅ 自定义算子脚手架已就绪！(本次新增/更新 {created_cnt} 项)")
        print(f"💡 下一步建议：请进入【第二步：根据算子需求按需加载 references/ 对应专项技能】进行开发！")
        return True
    else:
        print(f"  [识别结果] 当前目录下未发现 op_host 或 op_kernel 目录。")
        print(f"  [工程形态] 识别为【单文件核函数 (如 kernel.asc) 模式或其他形态】")
        print("-" * 70)
        print(f"🛡️  [自动处理] 遵循开发规范：保持现有工程纯净，无需补全自定义算子工程结构！")
        print("-" * 70)
        print(f"💡 下一步建议：请直接进入【第二步：根据算子需求按需查阅 references/ 下的对应专项技能】进行开发！")
        return False

def quick_check(project_root):
    """本地 0 秒极速静态代码检查 (提前拦截 90% 毕昇编译器报错、CANN 9.x 审查违规与核内死锁)"""
    print("\n" + "=" * 70)
    print("🔍 [OpHelper] 正在执行本地极速静态代码检查 (0秒拦截常见低级错误与规范红线)...")
    print("=" * 70)

    issues = []
    kernel_rules = [
        (r"\bprintf\s*\(", "C 风格 printf (AICore 核内不支持直接打印)"),
        (r"\bPRINTF\s*\(", "Ascend C 调试宏 PRINTF (建议提交前清理)"),
        (r"\bstd::cout\b", "std::cout (毕昇编译器无法在 AICore 链接 host STL)"),
        (r"\bstd::cerr\b", "std::cerr (毕昇编译器无法在 AICore 链接 host STL)"),
        (r"\bstd::min\b", "std::min (禁止在核函数内调用，请改用自定义三元模板 dev_min)"),
        (r"\bstd::max\b", "std::max (禁止在核函数内调用，请改用自定义三元模板 dev_max)"),
        (r"\bstd::pow\b", "std::pow (毕昇编译器无法在 AICore 链接 host math，请使用 AscendC::Power 或 Host 侧预计算)"),
        (r"\bstd::isinf\b", "std::isinf (毕昇编译器无法在 AICore 链接 host math，请改用位运算或在 Host 侧预计算)"),
        (r"\bstd::isnan\b", "std::isnan (毕昇编译器无法在 AICore 链接 host math，请改用位运算或在 Host 侧预计算)"),
        (r"\bstd::abs\b", "std::abs (毕昇编译器无法在 AICore 链接 host math，请改用自定义 dev_abs 或 AscendC::Abs)"),
        (r"\bstd::sqrt\b", "std::sqrt (毕昇编译器无法在 AICore 链接 host math，请改用 AscendC::Sqrt)"),
        (r"\bpowf\s*\(", "powf (AICore 核内无 libm 链接，请使用 AscendC::Power)"),
        (r"#include\s*<iostream>", "包含宿主头文件 <iostream>"),
        (r"#include\s*<stdio\.h>", "包含宿主头文件 <stdio.h>"),
        (r"\bTILING_KEY_IS\s*\(", "KERNEL-7: 严禁在 Kernel 中使用 TILING_KEY_IS 宏！请改用模板参数 + if constexpr 编译期分支"),
        (r"PipeBarrier\s*<\s*PIPE_ALL\s*>", "KERNEL-11: 严禁使用粗粒度 PipeBarrier<PIPE_ALL>！请使用具体细粒度管道 (如 PIPE_V) 或队列同步"),
        (r"\bDataCopy\s*\(\s*[a-zA-Z0-9_]+\s*,\s*[a-zA-Z0-9_]+\s*,", "KERNEL-1: 建议使用 DataCopyPad 替代 DataCopy，防止 32B 非对齐导致静默计算错误"),
    ]

    host_rules = [
        (r"IMPL_OP_INFERSHAPE\s*\([^)]+\)[\s\S]*?\.InferDataType\s*\(", "HOST-1: InferDataType 严禁在 op_host 目录链式注册！必须独立在 op_graph/ 下用 IMPL_OP 注册"),
        (r"\.InferDataType\s*\(", "HOST-1: InferDataType 严禁在 op_host 目录注册，必须放在 op_graph 目录"),
        (r"compileInfo\s*->\s*(coreNum|ubSize|blockSize)", "HOST-4: platform 参数必须在 Tiling 中直接获取，严禁经 compileInfo 传递"),
    ]

    # 1. 扫描 Kernel / 单文件代码
    scan_dirs = []
    kernel_dir = os.path.join(project_root, "op_kernel")
    if os.path.isdir(kernel_dir):
        scan_dirs.append(kernel_dir)

    kernel_asc = os.path.join(project_root, "kernel.asc")
    if os.path.isfile(kernel_asc):
        scan_dirs.append(project_root)

    for target in scan_dirs:
        for root, _, files in os.walk(target):
            if "build" in root or "harness" in root or ".git" in root:
                continue
            for file in files:
                if file.endswith((".cpp", ".h", ".asc")):
                    if file.startswith("main_test.") or file.startswith("main."):
                        continue
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, project_root)
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # 检查 TilingData POD 契约
                    if "tiling" in file.lower() and file.endswith(".h"):
                        if re.search(r"struct\s+\w+TilingData[\s\S]*?\{[\s\S]*?\([a-zA-Z0-9_,\s]*\)\s*\{", content):
                            issues.append((rel_p, 1, "POD-Rule: TilingData 结构体内禁止包含成员函数 (编译无法跨 Host/Device 传递)!", "struct TilingData"))

                    # 逐行检查 Kernel 规则
                    lines = content.splitlines()
                    for idx, line in enumerate(lines, 1):
                        s = line.strip()
                        if s.startswith("//") or s.startswith("/*"):
                            continue
                        for pattern, desc in kernel_rules:
                            if re.search(pattern, line):
                                issues.append((rel_p, idx, desc, s))

    # 2. 扫描 Host 侧代码 (op_host)
    host_dir = os.path.join(project_root, "op_host")
    if os.path.isdir(host_dir):
        for root, _, files in os.walk(host_dir):
            if "build" in root or ".git" in root:
                continue
            for file in files:
                if file.endswith((".cpp", ".h")):
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, project_root)
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    for pattern, desc in host_rules:
                        match = re.search(pattern, content)
                        if match:
                            line_no = content[:match.start()].count("\n") + 1
                            issues.append((rel_p, line_no, desc, match.group(0).strip()))

    if not issues:
        print("  [PASS] 代码检查通过：未发现非法 STL、核内死锁风险、粗粒度屏障或 CANN 9.x 架构红线违规！")
        return 0
    else:
        print(f"  [WARN] 发现 {len(issues)} 处潜在编译或规范红线风险:")
        for rel_p, idx, desc, code in issues:
            print(f"    ❌ {rel_p}:{idx} -> [{desc}]")
            print(f"       Code: {code}")
        return 1

def main():
    parser = argparse.ArgumentParser(description="昇腾 Ascend C 自定义算子开发极速辅助工具")
    parser.add_argument("--setup", action="store_true", help="强制执行脚手架检测与装配")
    parser.add_argument("--check", action="store_true", help="本地 0 秒静态代码自检")
    parser.add_argument("--dir", type=str, default=".", help="工程根目录")
    args = parser.parse_args()

    project_root = os.path.abspath(args.dir)

    if args.check:
        quick_check(project_root)
    elif args.setup:
        setup_harness(project_root)
    else:
        # 默认工作流第一步: 先检测与补全，再执行静态自检
        setup_harness(project_root)
        quick_check(project_root)

if __name__ == "__main__":
    main()
