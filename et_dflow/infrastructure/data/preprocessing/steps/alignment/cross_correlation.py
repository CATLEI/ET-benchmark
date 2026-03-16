import argparse
import numpy as np

def cross_correlation_align(data, tilt_angles=None):
    """
    通过傅里叶空间的互相关方法，对齐投影序列。
    
    该函数实现了电子显微镜断层扫描(ET)中投影图像序列的自动对齐算法。
    使用频域互相关技术来检测和修正图像间的平移偏移，确保重建质量。
    
    Args:
        data: 3D numpy数组，形状为(H, W, N)，其中H和W是图像尺寸，N是投影数量
        tilt_angles: 可选，1D数组，包含每个投影对应的倾斜角度
    
    Returns:
        tiltSeries: 对齐后的3D图像序列
        offsets: 2D数组，形状为(N, 2)，记录每个投影的x和y方向平移量
    """
    # 转换为浮点型以确保计算精度
    tiltSeries = data.astype(float)
    
    # 检查并修正数据维度
    if tiltSeries.ndim == 4:
        # 4D数组可能是 (H, W, channels, N) 或 (H, W, N, channels)
        print(f"警告：检测到4D数组，形状: {tiltSeries.shape}")
        # 判断哪个维度是通道维度（通常通道数较小，如1, 3, 4）
        shape = tiltSeries.shape
        # 假设通道维度是较小的那个（除了H和W之外）
        # 通常通道维度在位置2或3
        if shape[2] < shape[3] and shape[2] <= 4:
            # 可能是 (H, W, channels, N)
            print(f"检测到格式可能是 (H, W, channels={shape[2]}, N={shape[3]})")
            # 转换为灰度图：如果是多通道，取平均值；如果是单通道，直接使用
            if shape[2] > 1:
                print(f"将多通道图像转换为灰度图（取平均值）")
                tiltSeries = np.mean(tiltSeries, axis=2)  # 形状变为 (H, W, N)
            else:
                tiltSeries = tiltSeries[:, :, 0, :]  # 形状变为 (H, W, N)
        elif shape[3] < shape[2] and shape[3] <= 4:
            # 可能是 (H, W, N, channels)
            print(f"检测到格式可能是 (H, W, N={shape[2]}, channels={shape[3]})")
            if shape[3] > 1:
                print(f"将多通道图像转换为灰度图（取平均值）")
                tiltSeries = np.mean(tiltSeries, axis=3)  # 形状变为 (H, W, N)
            else:
                tiltSeries = tiltSeries[:, :, :, 0]  # 形状变为 (H, W, N)
        else:
            # 无法确定，尝试转置或使用第一个通道
            print(f"无法确定通道维度，尝试转置为 (H, W, N)")
            # 假设是 (H, W, channels, N)，取第一个通道
            tiltSeries = tiltSeries[:, :, 0, :]  # 形状变为 (H, W, N)
        print(f"转换后形状: {tiltSeries.shape}")
    elif tiltSeries.ndim != 3:
        raise ValueError(f"输入数据必须是3D或4D数组，但得到 {tiltSeries.ndim}D 数组，形状: {tiltSeries.shape}")
    
    # 确保维度顺序是 (H, W, N)
    if tiltSeries.shape[0] < tiltSeries.shape[2] and tiltSeries.shape[1] < tiltSeries.shape[2]:
        # 如果第三个维度最大，可能是 (N, H, W)，需要转置
        print(f"警告：检测到维度顺序可能是 (N, H, W)，将转置为 (H, W, N)")
        print(f"原始形状: {tiltSeries.shape}")
        tiltSeries = np.transpose(tiltSeries, (1, 2, 0))
        print(f"转置后形状: {tiltSeries.shape}")
    
    Nproj = tiltSeries.shape[2]  # 投影数量
    Ny, Nx = tiltSeries.shape[0], tiltSeries.shape[1]  # 图像尺寸
    
    # ========== 参考帧选择策略 ==========
    # 优先选择0度倾斜角度的图像作为参考帧，这通常是最稳定的
    referenceIndex = 0
    if tilt_angles is not None:
        # 验证角度数组长度
        if len(tilt_angles) != Nproj:
            print(f"警告：角度数组长度 ({len(tilt_angles)}) 与投影数量 ({Nproj}) 不匹配")
            print(f"将使用中间帧作为参考帧")
            referenceIndex = Nproj // 2
        else:
            # 查找0度倾斜角度的图像索引（允许0度附近的小误差）
            zeroDegreeTiltImage = np.where(np.abs(tilt_angles) < 0.1)[0]
            if zeroDegreeTiltImage.size > 0:
                referenceIndex = zeroDegreeTiltImage[0]
                # 安全检查：确保 referenceIndex 在有效范围内
                if referenceIndex >= Nproj:
                    print(f"警告：0度角度索引 ({referenceIndex}) 超出图像数量 ({Nproj})")
                    referenceIndex = Nproj // 2
            else:
                referenceIndex = Nproj // 2
    else:
        referenceIndex = Nproj // 2  # 没有角度信息时，使用中间帧作为参考
    
    # 输出调试信息
    print(f"参考帧索引: {referenceIndex}, 投影总数: {Nproj}")
    if tilt_angles is not None and referenceIndex < len(tilt_angles):
        print(f"参考帧角度: {tilt_angles[referenceIndex]:.2f} 度")
    
    # ========== 频域滤波器设计 ==========
    # 创建低通滤波器，用于减少高频噪声对互相关的影响
    filterCutoff = 4  # 截止频率参数，控制滤波器的锐度
    ky = np.fft.fftfreq(Ny)  # y方向频率坐标
    kx = np.fft.fftfreq(Nx)  # x方向频率坐标
    [kX, kY] = np.meshgrid(kx, ky)  # 创建频率网格
    kR = np.sqrt(kX**2 + kY**2)  # 径向频率
    
    # 设计平滑的低通滤波器：在截止频率内使用正弦平方函数
    # 这种设计可以避免频域中的振铃效应
    kFilter = (kR <= (0.5 / filterCutoff)) * np.sin(2 * filterCutoff * np.pi * kR)**2
    
    # ========== 空间域窗函数设计 ==========
    # 创建正弦窗函数，用于减少图像边缘的不连续性
    # 这可以避免FFT中的周期性假设导致的边缘效应
    y = np.linspace(1, Ny, Ny)  # y坐标
    x = np.linspace(1, Nx, Nx)  # x坐标
    [X, Y] = np.meshgrid(x, y)  # 创建空间网格
    
    # 正弦窗函数：在图像边缘处平滑过渡到0
    rFilter = (np.sin(np.pi * X / Nx) * np.sin(np.pi * Y / Ny)) ** 2
    
    # ========== 初始化偏移量记录 ==========
    offsets = np.zeros((Nproj, 2))  # 记录每个投影的x和y方向平移量
    
    # ========== 双向对齐过程 ==========
    # 从参考帧开始，向两个方向进行对齐，确保所有图像都与参考帧对齐
    
    # 向后对齐：从参考帧到最后一个投影
    for i in range(referenceIndex, Nproj - 1):
        # 确保切片返回2D数组
        img_current = tiltSeries[:, :, i + 1].copy()  # 使用 copy() 确保是独立的2D数组
        img_ref = tiltSeries[:, :, i].copy()
        offsets[i + 1, :], aligned_img = crossCorrelationAlign(
            img_current, img_ref, rFilter, kFilter)
        tiltSeries[:, :, i + 1] = aligned_img
    
    # 向前对齐：从参考帧到第一个投影
    for i in range(referenceIndex, 0, -1):
        img_current = tiltSeries[:, :, i - 1].copy()
        img_ref = tiltSeries[:, :, i].copy()
        offsets[i - 1, :], aligned_img = crossCorrelationAlign(
            img_current, img_ref, rFilter, kFilter)
        tiltSeries[:, :, i - 1] = aligned_img
    
    # ========== 平移量修正 ==========
    # 处理大于图像尺寸一半的平移量，利用FFT的周期性特性进行修正
    # 这样可以避免错误的平移检测（由于FFT的周期性边界条件）
    
    # 修正x方向平移量
    indices_X = np.where(offsets[:, 0] > Ny / 2)
    offsets[indices_X, 0] -= Ny
    
    # 修正y方向平移量
    indices_Y = np.where(offsets[:, 1] > Nx / 2)
    offsets[indices_Y, 1] -= Nx
    
    return tiltSeries, offsets, referenceIndex

def crossCorrelationAlign(image, reference, rFilter, kFilter):
    """
    执行两个图像之间的互相关对齐。
    
    该函数实现了基于傅里叶变换的互相关算法，用于检测两个图像之间的最佳平移量。
    通过频域计算可以显著提高计算效率，特别是在处理大图像时。
    
    Args:
        image: 待对齐的图像（2D numpy数组）
        reference: 参考图像（2D numpy数组）
        rFilter: 空间域窗函数，用于减少边缘效应
        kFilter: 频域滤波器，用于减少噪声影响
    
    Returns:
        shifts: 检测到的平移量 (y_shift, x_shift)
        output: 对齐后的图像
    """
    # ========== 图像预处理 ==========
    # 确保输入是2D数组
    if image.ndim != 2:
        if image.ndim == 3:
            # 如果是3D数组，取第一个切片或最后一个切片
            print(f"警告：image 是3D数组，形状: {image.shape}，将使用第一个切片")
            image = image[:, :, 0]
        else:
            raise ValueError(f"image 必须是2D数组，但得到 {image.ndim}D 数组，形状: {image.shape}")
    
    if reference.ndim != 2:
        if reference.ndim == 3:
            print(f"警告：reference 是3D数组，形状: {reference.shape}，将使用第一个切片")
            reference = reference[:, :, 0]
        else:
            raise ValueError(f"reference 必须是2D数组，但得到 {reference.ndim}D 数组，形状: {reference.shape}")
    
    # 去除均值并应用空间域窗函数
    # 去均值可以减少光照变化的影响，窗函数可以减少边缘效应
    image_f = np.fft.fft2((image - np.mean(image)) * rFilter)
    reference_f = np.fft.fft2((reference - np.mean(reference)) * rFilter)
    
    # ========== 频域互相关计算 ==========
    # 计算归一化互相关：conj(image_f) * reference_f
    # 这等价于在空间域中计算image与reference的互相关
    # 应用频域滤波器以减少噪声影响
    xcor = abs(np.fft.ifft2(np.conj(image_f) * reference_f * kFilter))
    
    # ========== 峰值检测 ==========
    # 找到互相关函数的峰值位置，这对应于最佳平移量
    shifts = np.unravel_index(xcor.argmax(), xcor.shape)
    
    # ========== 图像对齐 ==========
    # 根据检测到的平移量对图像进行平移
    output = np.roll(image, shifts[0], axis=0)  # y方向平移
    output = np.roll(output, shifts[1], axis=1)  # x方向平移
    
    return shifts, output

def main():
    """
    主函数：处理命令行参数并执行图像序列对齐。
    
    该函数提供了完整的命令行接口，支持批量处理图像序列，
    并可选择保存对齐后的图像和平移参数。
    """
    from io_utils import load_image_stack, save_image_stack, save_npy, load_angles
    # ========== 命令行参数解析 ==========
    parser = argparse.ArgumentParser(description='批量互相关对齐')
    parser.add_argument('input_folder', help='输入图像文件夹路径')
    parser.add_argument('output_folder', help='输出图像文件夹路径')
    parser.add_argument('--angles', default=None, help='可选，倾斜角度文件路径')
    parser.add_argument('--out_npy', default=None, help='可选，保存对齐后数据为npy文件')
    parser.add_argument('--out_offsets', default=None, help='可选，保存平移参数为npy文件')
    parser.add_argument('--save_reference', action='store_true', help='保存参考帧图像')
    args = parser.parse_args()
    
    # ========== 数据加载 ==========
    # 加载图像序列，返回3D数组和文件名列表
    data, files = load_image_stack(args.input_folder)
    
    # 加载倾斜角度信息（如果提供）
    tilt_angles = None
    if args.angles:
        tilt_angles = load_angles(args.angles)
        # 验证角度数组长度与图像数量是否匹配
        if len(tilt_angles) != data.shape[2]:
            print(f"警告：角度数组长度 ({len(tilt_angles)}) 与图像数量 ({data.shape[2]}) 不匹配")
            print(f"将截取角度数组的前 {data.shape[2]} 个元素")
            tilt_angles = tilt_angles[:data.shape[2]]
    
    # ========== 执行对齐算法 ==========
    # 调用主要的对齐函数
    aligned, offsets, referenceIndex = cross_correlation_align(data, tilt_angles)
    
    # ========== 数据保存 ==========
    # 修正：保存前clip并转uint8，确保图像数据在有效范围内
    aligned_save = np.clip(aligned, 0, 255).astype(np.uint8)
    
    # 保存对齐后的图像序列
    save_image_stack(aligned_save, args.output_folder, prefix='aligned', file_names=files)
    
    # 可选：保存原始浮点数据（用于后续处理）
    if args.out_npy:
        save_npy(aligned, args.out_npy)
    
    # 可选：保存平移参数（用于分析或调试）
    if args.out_offsets:
        save_npy(offsets, args.out_offsets)
    
    # ========== 保存参考帧 ==========
    if args.save_reference:
        import os
        from PIL import Image
        
        # 确保输出文件夹存在
        os.makedirs(args.output_folder, exist_ok=True)
        
        # 获取参考帧图像
        reference_image = aligned[:, :, referenceIndex]
        
        # 转换为uint8格式
        reference_image_uint8 = np.clip(reference_image, 0, 255).astype(np.uint8)
        
        # 生成参考帧文件名
        angle_info = ""
        if tilt_angles is not None:
            angle_info = f"_angle_{tilt_angles[referenceIndex]:.2f}deg"
        
        reference_filename = f"reference_frame_index_{referenceIndex:03d}{angle_info}.png"
        reference_path = os.path.join(args.output_folder, reference_filename)
        
        # 保存参考帧
        Image.fromarray(reference_image_uint8).save(reference_path)
        
        print(f"参考帧已保存: {reference_path}")
        print(f"参考帧信息: 索引={referenceIndex}, 角度={tilt_angles[referenceIndex] if tilt_angles is not None else '未知'}")

if __name__ == '__main__':
    main() 