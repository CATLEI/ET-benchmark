import argparse
import numpy as np
import scipy.ndimage
from typing import Dict, Any

def downsample2(data):
    """
    将三维体数据按2倍下采样（每个维度缩小一半），三线性插值。
    data: (H, W, N).
    """
    zoom = (0.5, 0.5, 1)
    result = scipy.ndimage.zoom(data, zoom, order=1, mode='constant', cval=0.0, prefilter=False)
    return result


def downsample(signal, params: Dict[str, Any]):
    """Pipeline adapter: (signal, params) -> signal. factor from params (default 2)."""
    factor = params.get("factor", 2)
    if factor <= 1:
        return signal.deepcopy()
    data = np.asarray(signal.data)  # (N, H, W)
    data_hwn = np.transpose(data, (1, 2, 0))
    zoom_factor = 1.0 / factor
    zoom = (zoom_factor, zoom_factor, 1)
    result = scipy.ndimage.zoom(data_hwn, zoom, order=1, mode='constant', cval=0.0, prefilter=False)
    out = signal.deepcopy()
    out.data = np.transpose(result, (2, 0, 1))
    return out


def main():
    from io_utils import load_image_stack, save_image_stack, save_npy
    parser = argparse.ArgumentParser(description='批量下采样（2倍）')
    parser.add_argument('input_folder', help='输入图像文件夹')
    parser.add_argument('output_folder', help='输出图像文件夹')
    parser.add_argument('--out_npy', default=None, help='可选，保存为npy文件')
    args = parser.parse_args()
    data, files = load_image_stack(args.input_folder)
    print("In downsample2:")
    print("data.shape:", data.shape)         
    print("files count:", len(files))  
    data_ds = downsample2(data)
    # 修正：保存时传递file_names参数，保持输出格式与输入一致
    data_ds_save = np.clip(data_ds, 0, 255).astype(np.uint8)
    print("data_ds_save.shape:", data_ds_save.shape)   
    save_image_stack(data_ds_save, args.output_folder, prefix='down2', file_names=files)
    if args.out_npy:
        save_npy(data_ds, args.out_npy)

if __name__ == '__main__':
    main() 