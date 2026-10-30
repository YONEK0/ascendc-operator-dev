# AdaptiveAvgPool2dGrad 自定义算子工程

## 1. 算子描述
本工程实现自适应二维平均池化反向传播（Adaptive Average Pooling 2D Gradient）算子。
- **输入 1 (grad_output)**: 输出特征图对应的梯度张量，Shape 为 `[N, C, H_out, W_out]`。
- **输入 2 (orig_input_shape)**: 原输入特征图尺寸参数 `[N, C, H_in, W_in]`。
- **输出 (grad_input)**: 原输入特征图计算所得梯度张量，Shape 为 `[N, C, H_in, W_in]`。

## 2. 工程目录结构
```
sampleproject/
├── CMakeLists.txt              # 顶级构建配置文件
├── README.md                   # 算子说明文档
├── op_host/                    # Host 侧代码（算子原型、Shape 推导、Tiling 切分）
│   ├── CMakeLists.txt
│   └── adaptive_avg_pool2d_grad.cpp
├── op_kernel/                  # Kernel 侧代码（AI Core 核心计算实现）
│   ├── CMakeLists.txt
│   ├── adaptive_avg_pool2d_grad_tiling.h
│   ├── tiling_key_adaptive_avg_pool2d_grad.h
│   └── adaptive_avg_pool2d_grad.cpp
└── harness/                    # 开发与测试脚手架（本地辅助工具，不参与最终提交）
    ├── gen_golden.py           # 自动生成测试数据与 Golden
    ├── check_cleanliness.py    # 零调试代码自检脚本
    ├── pack_submission.py      # 白名单纯净打包（本地生成 zip，无网络上传）
    └── README.md
```

## 3. 支持的数据类型
- Float32 (单精度浮点)
- BFloat16 / Float16 (可扩展)
