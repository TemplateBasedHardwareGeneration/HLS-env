from hls_script import hls_evaluation, print_result
import os

def verify_hls_code(code_str: str, top_function: str = "top", target_device: str = "xczu7ev-ffvc1156-2-e", 
                  clock_period: float = 5.0, vivado_hls_path: str = None, header_files: dict = None) -> dict:
    """
    验证HLS代码
    
    :param code_str: HLS C/C++代码字符串
    :param top_function: 顶层函数名
    :param target_device: 目标设备
    :param clock_period: 时钟周期（ns）
    :param vivado_hls_path: Vivado HLS路径
    :param header_files: 头文件字典，格式为 {"文件名": "文件内容"}
    :return: HLS评估结果
    """
    # 创建build目录
    build_dir = os.path.join(os.getcwd(), "build")
    os.makedirs(build_dir, exist_ok=True)
    
    # 如果提供了头文件，先写入头文件
    if header_files:
        for filename, content in header_files.items():
            header_path = os.path.join(build_dir, filename)
            with open(header_path, "w") as f:
                f.write(content)
    
    # 调用hls_evaluation函数进行评估
    return hls_evaluation(code_str, top_function, target_device, clock_period, vivado_hls_path)

if __name__ == "__main__":
    # 测试带有未知循环次数的函数
    code_str = """
int shift_func(int *in1, int *in2, int *outA, int *outB)
{
	*outA = *in1 >> 1;
	*outB = *in2 >> 2;
}

void hier_func4(int A, int B, int *C, int *D)
{
 	int apb, amb;

#ifndef __SYNTHESIS__
 	FILE *fp1; // The following code is ignored for synthesis
 	char filename[255];
 	sprintf(filename,Out_apb_%03d.dat,apb);
 	fp1=fopen(filename,w);
 	fprintf(fp1, %d \n, apb);
 	fclose(fp1);
#endif
 	shift_func(&apb,&amb,C,D);
}
"""

    # 选择要测试的代码
    test_code = code_str  # 测试带有未知循环次数的函数
    test_function = "hier_func4"
    
    # 运行测试
    result = verify_hls_code(test_code, test_function)
    print_result(result) 