#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Harness 工具 3: 本地打包工具

功能:
1. 提交前自动执行纯净度扫描（可跳过）。
2. 默认生成官方白名单的纯净提交包（仅 op_host / op_kernel / CMakeLists.txt / README.md / kernel.asc）。
3. --full 生成包含 run.sh、main_test.asc、harness/ 的完整工程包，便于分享或本地复现。
4. 不包含任何网络上传或平台相关逻辑。
"""

import argparse
import os
import subprocess
import sys
import zipfile

ALLOWED_DIRS = {"op_host", "op_kernel"}
ALLOWED_FILES = {"CMakeLists.txt", "README.md", "kernel.asc"}
ALLOWED_EXTS = {".cpp", ".h", ".c", ".txt", ".md", ".asc"}

IGNORE_PARTS = {
    "build", "build-npu", "build-cpu", ".git", ".idea", ".vscode",
    "__pycache__", ".pytest_cache", "submission.zip", "project_full.zip",
    "submission_clean.zip", "data",
}


def should_ignore(path):
    parts = path.replace("\\", "/").split("/")
    return any(part in IGNORE_PARTS or part.endswith(".pyc") for part in parts)


def create_clean_package(project_root, output_zip_path):
    """只收录官方评测所需的白名单文件"""
    print(f"[Pack] 正在创建纯净提交包: {output_zip_path}")
    count = 0
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_root):
            rel_root = os.path.relpath(root, project_root)
            if rel_root == ".":
                for f in files:
                    if f in ALLOWED_FILES:
                        zipf.write(os.path.join(root, f), f)
                        print(f"  + [Root] {f}")
                        count += 1
            else:
                top_dir = rel_root.split(os.sep)[0]
                if top_dir in ALLOWED_DIRS:
                    for f in files:
                        if any(f.endswith(ext) for ext in ALLOWED_EXTS):
                            full_p = os.path.join(root, f)
                            arc_name = os.path.join(rel_root, f).replace("\\", "/")
                            zipf.write(full_p, arc_name)
                            print(f"  + [{top_dir}] {arc_name}")
                            count += 1
    print(f"[Pack] 完成，共收录 {count} 个文件；已剔除 run.sh、main_test.asc、harness/、编译产物与测试数据。")
    return count


def create_full_package(project_root, output_zip_path):
    """收录完整工程（含本地评测驱动），用于分享或复现"""
    print(f"[Pack] 正在创建完整工程包: {output_zip_path}")
    count = 0
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_root):
            rel_root = os.path.relpath(root, project_root)
            if rel_root != "." and should_ignore(rel_root):
                continue
            for f in files:
                rel_path = os.path.normpath(os.path.join(rel_root, f))
                if should_ignore(rel_path):
                    continue
                zipf.write(os.path.join(root, f), rel_path.replace("\\", "/"))
                count += 1
    print(f"[Pack] 完成，共收录 {count} 个文件。")
    return count


def main():
    parser = argparse.ArgumentParser(description="算子工程本地打包工具（纯净提交包 / 完整工程包）")
    parser.add_argument("--dir", type=str, default=None, help="工程根目录（默认 harness 的上一级）")
    parser.add_argument("--out", type=str, default=None, help="输出 zip 路径")
    parser.add_argument("--full", action="store_true", help="打包完整工程（含 run.sh / main_test.asc / harness）")
    parser.add_argument("--skip-check", action="store_true", help="跳过纯净度检查")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(args.dir) if args.dir else os.path.abspath(os.path.join(script_dir, ".."))

    if not args.skip_check:
        clean_script = os.path.join(script_dir, "check_cleanliness.py")
        if os.path.exists(clean_script):
            print("[Check] 正在执行纯净度检查...")
            ret = subprocess.call([sys.executable, clean_script, project_root])
            if ret != 0:
                print("[Abort] 纯净度检查未通过，已中止打包。")
                return 1
        else:
            print("[Check] 未找到 check_cleanliness.py，跳过。")

    if args.full:
        output_zip = args.out or os.path.join(project_root, "project_full.zip")
        create_full_package(project_root, output_zip)
    else:
        output_zip = args.out or os.path.join(project_root, "submission.zip")
        create_clean_package(project_root, output_zip)

    print(f"[Done] 输出: {output_zip}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
