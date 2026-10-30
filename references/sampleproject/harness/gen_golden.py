#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Harness 工具 1: Golden 参考数据生成器
支持通过 PyTorch 或纯 NumPy 计算 AdaptiveAvgPool2dGrad 的标准答案并导出二进制
"""

import os
import sys
import argparse
import numpy as np

def compute_adaptive_avg_pool2d_grad_numpy(grad_output, in_shape):
    """
    使用 NumPy 精确模拟 AdaptiveAvgPool2dGrad 的数学公式
    """
    N, C, H_out, W_out = grad_output.shape
    H_in, W_in = in_shape
    grad_input = np.zeros((N, C, H_in, W_in), dtype=np.float32)

    for h in range(H_in):
        oh_start = int(np.floor(h * H_out / H_in))
        oh_end   = int(np.ceil((h + 1) * H_out / H_in))
        for w in range(W_in):
            ow_start = int(np.floor(w * W_out / W_in))
            ow_end   = int(np.ceil((w + 1) * W_out / W_in))

            val = 0.0
            for oh in range(oh_start, oh_end):
                ih_start = int(np.floor(oh * H_in / H_out))
                ih_end   = int(np.ceil((oh + 1) * H_in / H_out))
                kh = ih_end - ih_start
                for ow in range(ow_start, ow_end):
                    iw_start = int(np.floor(ow * W_in / W_out))
                    iw_end   = int(np.ceil((ow + 1) * W_in / W_out))
                    kw = iw_end - iw_start
                    pool_size = kh * kw
                    val += grad_output[:, :, oh, ow] / pool_size
            grad_input[:, :, h, w] = val
    return grad_input

def main():
    parser = argparse.ArgumentParser(description="生成测试输入与 Golden 参考答案")
    parser.add_argument("--batch", type=int, default=1, help="Batch 维度 N")
    parser.add_argument("--channel", type=int, default=1, help="通道维度 C")
    parser.add_argument("--hin", type=int, default=4, help="原输入高度 H_in")
    parser.add_argument("--win", type=int, default=4, help="原输入宽度 W_in")
    parser.add_argument("--hout", type=int, default=2, help="输出高度 H_out")
    parser.add_argument("--wout", type=int, default=2, help="输出宽度 W_out")
    parser.add_argument("--outdir", type=str, default="data", help="输出二进制目录")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    np.random.seed(42)

    # 随机生成梯度输入
    grad_output = np.random.randn(args.batch, args.channel, args.hout, args.wout).astype(np.float32)

    # 优先尝试 PyTorch，如无则使用纯 Python/NumPy 模拟
    try:
        import torch
        t_in = torch.randn(args.batch, args.channel, args.hin, args.win, requires_grad=True)
        t_out = torch.nn.functional.adaptive_avg_pool2d(t_in, (args.hout, args.wout))
        t_grad_out = torch.from_numpy(grad_output)
        t_out.backward(t_grad_out)
        golden_grad_in = t_in.grad.numpy()
        print("[Harness] 使用 PyTorch autograd 计算得到标准 Golden 数据。")
    except ImportError:
        print("[Harness] 未检测到 PyTorch，使用内置精确 NumPy 算法计算 Golden 数据。")
        golden_grad_in = compute_adaptive_avg_pool2d_grad_numpy(grad_output, (args.hin, args.win))

    in_file = os.path.join(args.outdir, "input_grad.bin")
    out_file = os.path.join(args.outdir, "golden_output.bin")

    grad_output.tofile(in_file)
    golden_grad_in.tofile(out_file)

    print(f"[OK] 数据已生成:")
    print(f"  - 输入梯度: {in_file} (shape={grad_output.shape}, size={os.path.getsize(in_file)} bytes)")
    print(f"  - 黄金输出: {out_file} (shape={golden_grad_in.shape}, size={os.path.getsize(out_file)} bytes)")

if __name__ == "__main__":
    main()
