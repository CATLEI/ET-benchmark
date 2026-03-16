import argparse
import numpy as np
from scipy import ndimage

def calculateLineIntensity(Intensity_var, angle_d, N):
    Nx = Intensity_var.shape[0]  # 图像x方向尺寸
    Ny = Intensity_var.shape[1]  # 图像y方向尺寸
    cenx = np.floor(Nx / 2)  # x中心
    ceny = np.floor(Ny / 2)  # y中心
    ang = angle_d * np.pi / 180  # 角度转弧度
    w = np.zeros(N)  # 权重数组
    v = np.zeros(N)  # 强度数组
    for i in range(0, N):  # 沿直线采样
        x = i * np.cos(ang)
        y = i * np.sin(ang)
        sx = abs(np.floor(x) - x)
        sy = abs(np.floor(y) - y)
        px = int(np.floor(x) + cenx)
        py = int(np.floor(y) + ceny)
        if (px >= 0 and px < Nx and py >= 0 and py < Ny):
            w[i] = w[i] + (1 - sx) * (1 - sy)
            v[i] = v[i] + (1 - sx) * (1 - sy) * Intensity_var[px, py]
        px = int(np.ceil(x) + cenx)
        py = int(np.floor(y) + ceny)
        if (px >= 0 and px < Nx and py >= 0 and py < Ny):
            w[i] = w[i] + sx * (1 - sy)
            v[i] = v[i] + sx * (1 - sy) * Intensity_var[px, py]
        px = int(np.floor(x) + cenx)
        py = int(np.ceil(y) + ceny)
        if (px >= 0 and px < Nx and py >= 0 and py < Ny):
            w[i] = w[i] + (1 - sx) * sy
            v[i] = v[i] + (1 - sx) * sy * Intensity_var[px, py]
        px = int(np.ceil(x) + cenx)
        py = int(np.ceil(y) + ceny)
        if (px >= 0 and px < Nx and py >= 0 and py < Ny):
            w[i] = w[i] + sx * sy
            v[i] = v[i] + sx * sy * Intensity_var[px, py]
    v[w != 0] = v[w != 0] / w[w != 0]  # 归一化
    return v  # 返回采样强度


def tilt_axis_rotation_align(data):
    tiltSeries = data.astype(float)  # 转为float，便于后续处理
    (Nslice, Nray, Nproj) = tiltSeries.shape  # 获取三维数据的尺寸
    Intensity = np.zeros(tiltSeries.shape)  # 用于存储每帧的频谱强度
    # 对每一帧做FFT
    for i in range(Nproj):
        tiltImage = tiltSeries[:, :, i]
        tiltImage_F = np.abs(np.fft.fft2(tiltImage))  # 取幅值谱
        if (i == 0):
            temp = tiltImage_F[0, 0]  # 归一化因子
        Intensity[:, :, i] = np.fft.fftshift(tiltImage_F / temp)  # 归一化并中心化
    Intensity = np.power(Intensity, 0.2)  # 增强对比
    Intensity_var = np.var(Intensity, axis=2)  # 计算方差图
    coarseStep = 2  # 粗步长
    fineStep = 0.1  # 细步长
    coarseAngles = np.arange(-90, 90, coarseStep)  # 粗搜索角度
    Nx = Intensity_var.shape[0]
    Ny = Intensity_var.shape[1]
    N = int(np.round(np.min([Nx, Ny]) // 3))  # 采样点数
    # 粗搜索
    I = np.zeros((coarseAngles.size, N))
    for a in range(coarseAngles.size):
        I[a, :] = calculateLineIntensity(Intensity_var, coarseAngles[a], N)
    I_sum = np.sum(I, axis=1)
    minIntensityIndex = np.argmin(I_sum)
    rot_ang = coarseAngles[minIntensityIndex]  # 粗略旋转角
    # 细搜索
    fineAngles = np.arange(rot_ang - coarseStep, rot_ang + coarseStep + fineStep, fineStep)
    I = np.zeros((fineAngles.size, N))
    for a in range(fineAngles.size):
        I[a, :] = calculateLineIntensity(Intensity_var, fineAngles[a], N)
    I_sum = np.sum(I, axis=1)
    minIntensityIndex = np.argmin(I_sum)
    rot_ang = fineAngles[minIntensityIndex]  # 精确旋转角
    # 旋转校正
    axes = (0, 1)
    result = ndimage.rotate(tiltSeries, -rot_ang, axes=axes, reshape=False, order=1)  # 旋转校正
    return result, rot_ang  # 返回校正后的数据和角度


def main():
    from io_utils import load_image_stack, save_image_stack, save_npy
    parser = argparse.ArgumentParser(description='自动倾斜轴旋转校正')  # 创建参数解析器
    parser.add_argument('input_folder', help='输入图像文件夹')  # 输入文件夹
    parser.add_argument('output_folder', help='输出图像文件夹')  # 输出文件夹
    parser.add_argument('--out_npy', default=None, help='可选，保存为npy文件')  # 可选参数，保存npy
    parser.add_argument('--out_angle', default=None, help='可选，保存旋转角度txt')  # 可选参数，保存角度
    args = parser.parse_args()  # 解析参数
    data, files = load_image_stack(args.input_folder)  # 读取输入图片和文件名
    rotated, rot_ang = tilt_axis_rotation_align(data)  # 自动旋转校正
    rotated_save = np.clip(rotated, 0, 255).astype(np.uint8)  # 裁剪到0-255并转为uint8

    save_image_stack(rotated_save, args.output_folder, prefix='rot_aligned', file_names=files)

    if args.out_npy:
        save_npy(rotated, args.out_npy)  # 如指定，保存npy
    if args.out_angle:
        with open(args.out_angle, 'w') as f:
            f.write(f'{rot_ang}\n')  # 保存旋转角度


if __name__ == '__main__':
    main()  # 作为脚本运行时，执行主函数 