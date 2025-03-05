import os
import re
import subprocess
import tempfile
from pathlib import Path
import shutil
import sys
import time

def find_vivado_hls():
    """
    尝试自动查找Vivado HLS的安装路径
    """
    # 常见的Vivado HLS安装路径
    common_paths = [
        r"C:\Xilinx\Vivado\2018.3\bin\vivado_hls.bat",
        r"C:\Xilinx\Vivado_HLS\2018.3\bin\vivado_hls.bat",
        r"D:\Xilinx\Vivado\2018.3\bin\vivado_hls.bat",
        r"D:\Xilinx\Vivado_HLS\2018.3\bin\vivado_hls.bat",
    ]
    
    # 检查常见路径
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    # 检查环境变量
    try:
        result = subprocess.run(["where", "vivado_hls"], check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        pass
    
    return None

def hls_evaluation(code_str: str, top_function: str = "top", target_device: str = "xczu7ev-ffvc1156-2-e", 
                  clock_period: float = 5.0, vivado_hls_path: str = None) -> dict:
    """
    HLS代码性能评估函数
    :param code_str: 输入的C/C++代码字符串
    :param top_function: 顶层函数名称
    :param target_device: 目标FPGA型号
    :param clock_period: 时钟周期(ns)
    :param vivado_hls_path: Vivado HLS可执行文件的路径，如果为None则尝试自动查找
    :return: 包含性能和资源消耗的字典
    """
    # 如果未指定Vivado HLS路径，尝试自动查找
    if vivado_hls_path is None:
        vivado_hls_path = find_vivado_hls()
        if vivado_hls_path:
            print(f"找到Vivado HLS: {vivado_hls_path}")
        else:
            return {
                "error": "找不到vivado_hls命令。请指定Vivado HLS的安装路径或将其添加到系统PATH中。",
                "raw_log": "Command 'vivado_hls' not found"
            }
    
    # 创建build目录
    build_dir = Path(os.getcwd()) / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(exist_ok=True)
    
    # 1. 生成HLS源代码文件
    src_file = build_dir / f"{top_function}.cpp"
    with open(src_file, "w", encoding="utf-8") as f:
        f.write(code_str)
    
    # 2. 生成TCL自动化脚本 - 修正TCL脚本，简化报告处理
    tcl_script = """
# Project settings
open_project -reset {0}_prj
add_files {1}
set_top {0}

# Create solution
open_solution -reset "solution1"
set_part {{{2}}}
create_clock -period {3} -name default

# Synthesis process
csynth_design

exit
""".format(top_function, src_file.name, target_device, clock_period)

    tcl_file = build_dir / "run.tcl"
    print(f"TCL脚本路径: {tcl_file}")
    with open(tcl_file, "w", encoding="utf-8") as f:
        f.write(tcl_script)

    # 3. 执行Vivado HLS
    try:
        print(f"执行命令: {vivado_hls_path} -f {str(tcl_file)}")
        proc = subprocess.run(
            [vivado_hls_path, "-f", str(tcl_file)],
            cwd=str(build_dir),
            capture_output=True,
            text=True
        )
        
        # 保存日志
        with open(build_dir / "vivado_hls.log", "w", encoding="utf-8") as f:
            f.write(proc.stdout)
            if proc.stderr:
                f.write("\n\nSTDERR:\n")
                f.write(proc.stderr)
        
        # 4. 检查执行结果
        if proc.returncode != 0:
            return {
                "error": f"HLS synthesis failed: {proc.stderr[-500:] if proc.stderr else proc.stdout[-500:]}",
                "raw_log": proc.stderr if proc.stderr else proc.stdout
            }

        # 5. 解析报告文件
        def parse_reports():
            # 查找报告文件
            report_file = None
            report_dir = build_dir / f"{top_function}_prj" / "solution1" / "syn" / "report"
            
            # 等待报告文件生成（最多等待5秒）
            max_wait = 5
            wait_time = 0
            while wait_time < max_wait:
                if report_dir.exists():
                    potential_report = report_dir / f"{top_function}_csynth.rpt"
                    if potential_report.exists():
                        report_file = potential_report
                        break
                time.sleep(1)
                wait_time += 1
                print(f"等待报告文件生成... {wait_time}/{max_wait}")
            
            if not report_file or not report_file.exists():
                print(f"找不到报告文件: {report_dir / f'{top_function}_csynth.rpt'}")
                # 尝试列出报告目录中的文件
                if report_dir.exists():
                    print(f"报告目录中的文件: {list(report_dir.glob('*'))}")
                return {
                    "error": "找不到报告文件",
                    "timing": {},
                    "latency": {},
                    "utilization": {}
                }
            
            print(f"找到报告文件: {report_file}")
            
            try:
                with open(report_file, encoding="utf-8") as f:
                    content = f.read()
                    
                    # 保存报告内容以便调试
                    with open(build_dir / "report_content.txt", "w", encoding="utf-8") as debug_f:
                        debug_f.write(content)
                    
                    # 创建结果字典
                    result = {
                        "timing": {},
                        "latency": {},
                        "utilization": {}
                    }
                    
                    # 解析Timing信息
                    timing_section = re.search(r"== Performance Estimates\s+=+\s+\+ Timing \(ns\):\s+\* Summary:\s+\+--------\+-------\+----------\+------------\+\s+\|  Clock \| Target\| Estimated\| Uncertainty\|\s+\+--------\+-------\+----------\+------------\+\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\+--------\+-------\+----------\+------------\+", content)
                    
                    if timing_section:
                        result["timing"] = {
                            "clock": timing_section.group(1).strip(),
                            "target": float(timing_section.group(2).strip()),
                            "estimated": float(timing_section.group(3).strip()),
                            "uncertainty": float(timing_section.group(4).strip())
                        }
                    
                    # 解析Latency信息
                    latency_section = re.search(r"\+ Latency \(clock cycles\):\s+\* Summary:\s+\+-----\+-----\+-----\+-----\+---------\+\s+\|  Latency  \|  Interval \| Pipeline\|\s+\| min \| max \| min \| max \|   Type  \|\s+\+-----\+-----\+-----\+-----\+---------\+\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\+-----\+-----\+-----\+-----\+---------\+", content)
                    
                    if latency_section:
                        result["latency"] = {
                            "min": int(latency_section.group(1).strip()),
                            "max": int(latency_section.group(2).strip()),
                            "interval_min": int(latency_section.group(3).strip()),
                            "interval_max": int(latency_section.group(4).strip()),
                            "pipeline_type": latency_section.group(5).strip()
                        }
                    
                    # 解析Utilization信息
                    utilization_section = re.search(r"== Utilization Estimates\s+=+\s+\* Summary:\s+\+-----------------\+---------\+-------\+--------\+--------\+-----\+\s+\|       Name      \| BRAM_18K\| DSP48E\|   FF   \|   LUT  \| URAM\|\s+\+-----------------\+---------\+-------\+--------\+--------\+-----\+\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\+-----------------\+---------\+-------\+--------\+--------\+-----\+\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\+-----------------\+---------\+-------\+--------\+--------\+-----\+\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\+-----------------\+---------\+-------\+--------\+--------\+-----\+\s+\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s+\+-----------------\+---------\+-------\+--------\+--------\+-----\+", content)
                    
                    if utilization_section:
                        # 提取总资源使用情况（Total行）
                        total_idx = 7  # Total行的索引
                        available_idx = 8  # Available行的索引
                        utilization_idx = 9  # Utilization行的索引
                        
                        # 使用一致的键名
                        result["utilization"] = {
                            "BRAM": int(utilization_section.group(total_idx * 6 + 2).strip()),
                            "DSP": int(utilization_section.group(total_idx * 6 + 3).strip()),  # 使用DSP而不是DSP48E
                            "FF": int(utilization_section.group(total_idx * 6 + 4).strip()),
                            "LUT": int(utilization_section.group(total_idx * 6 + 5).strip()),
                            "URAM": int(utilization_section.group(total_idx * 6 + 6).strip()),
                            "available": {
                                "BRAM": int(utilization_section.group(available_idx * 6 + 2).strip()),
                                "DSP": int(utilization_section.group(available_idx * 6 + 3).strip()),  # 使用DSP而不是DSP48E
                                "FF": int(utilization_section.group(available_idx * 6 + 4).strip()),
                                "LUT": int(utilization_section.group(available_idx * 6 + 5).strip()),
                                "URAM": int(utilization_section.group(available_idx * 6 + 6).strip())
                            },
                            "utilization_percentage": {
                                "BRAM": utilization_section.group(utilization_idx * 6 + 2).strip(),
                                "DSP": utilization_section.group(utilization_idx * 6 + 3).strip(),  # 使用DSP而不是DSP48E
                                "FF": utilization_section.group(utilization_idx * 6 + 4).strip(),
                                "LUT": utilization_section.group(utilization_idx * 6 + 5).strip(),
                                "URAM": utilization_section.group(utilization_idx * 6 + 6).strip()
                            }
                        }
                    
                    # 如果正则表达式匹配失败，尝试使用更简单的方法提取关键信息
                    if not result["timing"] or not result["latency"] or not result["utilization"]:
                        print("使用备用方法解析报告...")
                        
                        # 提取Timing信息
                        if not result["timing"]:
                            target_match = re.search(r"Target\|\s+\|[^|]+\|\s+([\d.]+)", content)
                            estimated_match = re.search(r"Estimated\|\s+\|[^|]+\|\s+([\d.]+)", content)
                            
                            if target_match and estimated_match:
                                result["timing"] = {
                                    "target": float(target_match.group(1)),
                                    "estimated": float(estimated_match.group(1))
                                }
                        
                        # 提取Latency信息
                        if not result["latency"]:
                            latency_match = re.search(r"\|\s+(\d+)\s+\|\s+(\d+)\s+\|\s+(\d+)\s+\|\s+(\d+)\s+\|\s+([a-z]+)\s+\|", content)
                            
                            if latency_match:
                                result["latency"] = {
                                    "min": int(latency_match.group(1)),
                                    "max": int(latency_match.group(2)),
                                    "interval_min": int(latency_match.group(3)),
                                    "interval_max": int(latency_match.group(4)),
                                    "pipeline_type": latency_match.group(5)
                                }
                        
                        # 提取Utilization信息
                        if not result["utilization"]:
                            bram_match = re.search(r"BRAM_18K\s+\|\s+(\d+)", content)
                            dsp_match = re.search(r"DSP48E\s+\|\s+(\d+)", content)
                            ff_match = re.search(r"FF\s+\|\s+(\d+)", content)
                            lut_match = re.search(r"LUT\s+\|\s+(\d+)", content)
                            
                            if bram_match and dsp_match and ff_match and lut_match:
                                result["utilization"] = {
                                    "BRAM": int(bram_match.group(1)),
                                    "DSP": int(dsp_match.group(1)),  # 使用DSP而不是DSP48E
                                    "FF": int(ff_match.group(1)),
                                    "LUT": int(lut_match.group(1))
                                }
                    
                    return result
            except Exception as e:
                print(f"解析报告文件时出错: {str(e)}")
                return {
                    "error": f"解析报告文件时出错: {str(e)}",
                    "timing": {},
                    "latency": {},
                    "utilization": {}
                }

        # 6. 返回结果
        report_results = parse_reports()
        
        return {
            "status": "success",
            "timing": report_results.get("timing", {}),
            "latency": report_results.get("latency", {}),
            "utilization": report_results.get("utilization", {}),
            "raw_log": proc.stdout
        }
    except Exception as e:
        return {
            "error": f"执行过程中发生错误: {str(e)}",
            "raw_log": f"Exception occurred during execution: {str(e)}"
        }

# 使用示例
if __name__ == "__main__":
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
    
    # 检查命令行参数，看是否提供了Vivado HLS路径
    vivado_hls_path = None
    if len(sys.argv) > 1:
        vivado_hls_path = sys.argv[1]
        print(f"使用指定的Vivado HLS路径: {vivado_hls_path}")
    
    # 如果没有提供路径，可以在这里手动指定
    # vivado_hls_path = r"C:\Xilinx\Vivado\2018.3\bin\vivado_hls.bat"
    
    result = hls_evaluation(test_code, vivado_hls_path=vivado_hls_path)
    print("HLS Evaluation Result:")
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print("Timing Information:")
        for key, value in result["timing"].items():
            print(f"  {key}: {value}")
        
        print("\nLatency Information:")
        for key, value in result["latency"].items():
            print(f"  {key}: {value}")
        
        print("\nResource Utilization:")
        # 打印基本资源使用情况
        for key, value in result["utilization"].items():
            if key not in ["available", "utilization_percentage"]:
                print(f"  {key}: {value}")
        
        # 打印可用资源
        if "available" in result["utilization"]:
            print("  Available Resources:")
            for key, value in result["utilization"]["available"].items():
                print(f"    {key}: {value}")
        
        # 打印使用百分比
        if "utilization_percentage" in result["utilization"]:
            print("  Utilization Percentage:")
            for key, value in result["utilization"]["utilization_percentage"].items():
                print(f"    {key}: {value}")
    
    print("完整日志保存在build目录中")