# HLS-env

## 项目简介

HLS-env 是一个用于评估 Xilinx HLS (High-Level Synthesis) 代码性能和资源消耗的 Python 工具。该工具可以自动化 HLS 代码的综合过程，并提取关键性能指标，帮助开发者快速评估 FPGA 实现效果。

## 前提条件

- 已安装 Xilinx Vivado HLS 2018.3
- Python 3.x

## 功能特点

- 自动查找 Vivado HLS 安装路径
- 生成 HLS 项目和 TCL 脚本
- 执行 HLS 综合流程
- 解析综合报告，提取关键性能指标：
- 时序信息（Timing）
- 延迟信息（Latency）
- 资源利用率（Resource Utilization）

## 使用方法

from hls_script import hls_evaluation

# 示例 HLS 代码

test_code = """

void top(int a[100], int b[100], int res[100]) {

    #pragma HLS INTERFACE m_axi port=a bundle=gmem

    #pragma HLS INTERFACE m_axi port=b bundle=gmem

    #pragma HLS INTERFACE m_axi port=res bundle=gmem

    for (int i = 0; i < 100; i++) {

    #pragma HLS PIPELINE II=1

    res[i] = a[i] + b[i];

    }

}

"""

# 执行评估

result = hls_evaluation(

code_str=test_code,

top_function="top", # 顶层函数名称

target_device="xczu7ev-ffvc1156-2-e", # 目标 FPGA 型号

clock_period=5.0, # 时钟周期(ns)

vivado_hls_path=None # 自动查找 Vivado HLS 路径

)
