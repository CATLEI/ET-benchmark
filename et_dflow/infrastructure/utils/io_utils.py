import os
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import tifffile  # 需要安装tifffile库

def load_image_stack(folder, ext=('tif', 'tiff', 'png', 'jpg', 'jpeg')):
    """
    读取文件夹下所有图片，按文件名排序，堆叠为3D numpy数组（H, W, N）。
    支持常见图片格式。
    """
    files = [f for f in os.listdir(folder) if f.lower().endswith(ext)]
    if not files:
        raise ValueError(f"No image files with extensions {ext} found in {folder}")
    files.sort()  # 按文件名排序
    imgs = []
    for fname in files:
        img = Image.open(os.path.join(folder, fname))
        imgs.append(np.array(img))
    
    stack = np.stack(imgs, axis=-1)  # (H, W, N)
    return stack, files

def save_image_stack(stack, out_folder, prefix='img', ext='tif', file_names=None):
    """
    将3D numpy数组（H, W, N）保存为图片序列。
    如果提供file_names，则按file_names的扩展名保存，否则使用ext参数。
    """
    os.makedirs(out_folder, exist_ok=True)
    N = stack.shape[-1]
    for i in range(N):
        img = stack[..., i]
        # 修正：float类型归一化到0-255并转uint8
        if np.issubdtype(img.dtype, np.floating):
            img = np.clip(img, 0, 255)
            img = img.astype(np.uint8)
        elif img.dtype == np.bool_:
            img = img.astype(np.uint8) * 255
        if file_names is not None and i < len(file_names):
            # 获取原始扩展名
            orig_ext = os.path.splitext(file_names[i])[1][1:]  # 去掉点
            fname = f"{prefix}_{i:04d}.{orig_ext}"
        else:
            #fname = f"{prefix}_{i:04d}.{ext}"
            fname = f"{prefix}_{i:04d}.png"
        img_path = os.path.join(out_folder, fname)
        Image.fromarray(img).save(img_path)
        # 强制刷新到磁盘（关键：确保数据真正写入）
        with open(img_path, 'rb') as f:
            os.fsync(f.fileno())  # 强制操作系统将缓存写入磁盘


def load_angles(angle_file):
    """
    读取角度文件（每行一个角度，支持逗号/空格分隔）。
    """
    with open(angle_file, 'r') as f:
        lines = f.readlines()
    angles = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for val in line.replace(',', ' ').split():
            angles.append(float(val))
    return np.array(angles)

def save_npy(array, out_path):
    np.save(out_path, array)

def load_npy(npy_path):
    return np.load(npy_path) 

def save_sinogram_image(sinogram, filename, transpose=False):
    """
    保存sinogram图像
    
    标准sinogram显示：
    - 横轴（X）：探测器位置/射线索引（Ray Index）
    - 纵轴（Y）：投影角度索引（Angle Index）
    
    Args:
        sinogram: 2D数组，形状为 (Nray, Nproj) 或 (Nproj, Nray)
        filename: 保存路径
        transpose: 是否需要转置（如果输入是(Nproj, Nray)格式）
    """
    plt.figure(figsize=(10, 8))
    
    # 如果需要转置，确保显示格式正确
    if transpose:
        sinogram_display = sinogram.T
    else:
        sinogram_display = sinogram
    
    # 显示sinogram
    im = plt.imshow(sinogram_display, cmap='gray', aspect='auto', origin='lower')
    plt.colorbar(im, label='Projection Intensity')
    
    # 设置坐标轴标签
    # 标准显示：X轴=探测器位置，Y轴=投影角度
    plt.xlabel('Ray Index (Detector Position)', fontsize=12)
    plt.ylabel('Projection Angle Index', fontsize=12)
    plt.title('Sinogram', fontsize=14, fontweight='bold')
    
    # 添加网格以便查看（可选）
    plt.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()

    

def stack_images_to_tiff(png_dir, output_tiff):
    # 获取所有PNG文件并按文件名排序
    png_files = sorted([f for f in os.listdir(png_dir) if f.lower().endswith('.png')])
    
    if not png_files:
        print("未找到PNG文件！")
        return
    
    # 创建TIFF写入器（使用BigTIFF格式支持大文件）
    with tifffile.TiffWriter(output_tiff, bigtiff=True) as tif:
        for i, filename in enumerate(png_files):
            img_path = os.path.join(png_dir, filename)
            
            # 使用PIL打开图像并转换为numpy数组
            with Image.open(img_path) as img:
                # 转换为RGB模式（如果原始是RGBA）
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                
                # 将图像数据转为numpy数组
                img_array = np.array(img)
            
            # 修复：使用 'compression' 参数代替 'compress'
            tif.write(img_array, 
                      compression='zlib',  # 使用ZLIB压缩
                      compressionargs={'level': 6},  # 压缩级别6（平衡）
                      photometric='minisblack' if img_array.ndim == 2 else 'rgb')
    
    print(f"成功创建 {len(png_files)} 层TIFF: {output_tiff}")

