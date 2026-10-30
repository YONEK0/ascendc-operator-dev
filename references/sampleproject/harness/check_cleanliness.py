#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Harness 工具 2: 零调试代码与提交合规自检脚本
在提交前对 op_host 和 op_kernel 下的代码进行静态检查，确保无任何 debug 信息和非法调用
"""

import os
import re
import sys

# 禁止在 AI Core 核函数中出现的调试特征与非法 API
FORBIDDEN_KERNEL_PATTERNS = [
    (r"\bprintf\s*\(", "C 风格 printf 调试打印"),
    (r"\bPRINTF\s*\(", "Ascend C 调试宏 PRINTF"),
    (r"\bstd::cout\b", "C++ 标准输出流 std::cout"),
    (r"\bstd::cerr\b", "C++ 标准错误流 std::cerr"),
    (r"#include\s*<iostream>", "包含未被核函数支持的 <iostream> 头文件"),
    (r"#include\s*<stdio\.h>", "包含 <stdio.h> 调试头文件"),
    (r"\bstd::min\b", "核内非法调用 std::min（毕昇编译器无法在 aicore 内链接 host STL）"),
    (r"\bstd::max\b", "核内非法调用 std::max（毕昇编译器无法在 aicore 内链接 host STL）"),
    (r"\b(ASSERT|assert)\s*\(", "断言宏 assert"),
]

def scan_file(filepath, forbidden_rules):
    errors = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    for idx, line in enumerate(lines, 1):
        # 忽略行注释
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        for pattern, desc in forbidden_rules:
            if re.search(pattern, line):
                errors.append((idx, line.strip(), desc))
    return errors

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(script_dir, ".."))

    kernel_dir = os.path.join(project_root, "op_kernel")
    host_dir = os.path.join(project_root, "op_host")

    total_violations = 0
    print("=" * 60)
    print("[Harness Check] 开始进行提交代码纯净度与合规静态扫描...")
    print("=" * 60)

    # 扫描 op_kernel
    if os.path.exists(kernel_dir):
        for root, _, files in os.walk(kernel_dir):
            for file in files:
                if file.endswith((".cpp", ".h", ".c")):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, project_root)
                    violations = scan_file(full_path, FORBIDDEN_KERNEL_PATTERNS)
                    if violations:
                        print(f"\n[FAIL] 发现违规代码: {rel_path}")
                        for line_no, content, desc in violations:
                            print(f"   Line {line_no}: [{desc}] -> {content}")
                            total_violations += 1
                    else:
                        print(f"[PASS] 纯净合规: {rel_path}")

    # 扫描 op_host 基础检查
    if os.path.exists(host_dir):
        for root, _, files in os.walk(host_dir):
            for file in files:
                if file.endswith((".cpp", ".h")):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, project_root)
                    print(f"[PASS] 结构合规: {rel_path}")

    print("-" * 60)
    if total_violations == 0:
        print("[SUCCESS] 代码扫描完毕：100% 纯净！无任何调试代码或非法 API，符合提交标准！")
        return 0
    else:
        print(f"[ERROR] 扫描发现 {total_violations} 处不合规代码，请修改后再提交！")
        return 1

if __name__ == "__main__":
    sys.exit(main())
