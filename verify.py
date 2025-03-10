from hls_script import hls_evaluation, print_result
import os

def verify_hls_code(code_str: str, top_function: str = "top", target_device: str = "xczu7ev-ffvc1156-2-e", 
                  clock_period: float = 5.0, vivado_hls_path: str = None) -> dict:
    """
    验证HLS代码
    
    :param code_str: HLS C/C++代码字符串
    :param top_function: 顶层函数名
    :param target_device: 目标设备
    :param clock_period: 时钟周期（ns）
    :param vivado_hls_path: Vivado HLS路径
    :return: HLS评估结果
    """
    
    # 调用hls_evaluation函数进行评估
    return hls_evaluation(code_str, top_function, target_device, clock_period, vivado_hls_path)

if __name__ == "__main__":

    code_str = """
int shift_func(int *in1, int *in2, double *outA, double *outB)
{
 *outA = *in1 >> 1;
 *outB = *in2 >> 2;
 return 0;
}

void hier_func4(int A, int B, double *C, double *D)
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
    
    result = verify_hls_code(code_str, "hier_func4")
    print_result(result) 