import argparse
import numpy as np
import os

def background_subtraction(data):
    """
    对每一帧图像做直方图分析，自动检测背景峰值并减去。
    data: (H, W, N) numpy array.
    """
    data_bs = data.astype(np.float32)
    for i in range(data.shape[2]):
        (hist, bins) = np.histogram(data[:, :, i].flatten(), 256)
        data_bs[:, :, i] = data_bs[:, :, i] - bins[np.argmax(hist)]
    return data_bs


def background_subtraction_signal(signal, params):
    """Pipeline adapter: (signal, params) -> signal. Hyperspy signal.data is (N, H, W)."""
    data = np.asarray(signal.data)
    if data.ndim != 3:
        raise ValueError(f"Expected 3D tilt series, got shape {data.shape}")
    data_hwn = np.transpose(data, (1, 2, 0))
    result = background_subtraction(data_hwn)
    out = signal.deepcopy()
    out.data = np.transpose(result, (2, 0, 1))
    return out

def main():
    from io_utils import load_image_stack, save_image_stack, save_npy
    parser = argparse.ArgumentParser(description='批量背景扣除')
    parser.add_argument('input_folder', help='输入图像文件夹')
    parser.add_argument('output_folder', help='输出图像文件夹')
    parser.add_argument('--out_npy', default=None, help='可选，保存为npy文件')
    args = parser.parse_args()

    data, files = load_image_stack(args.input_folder)
    data_bs = background_subtraction(data)
    # 修正：保存时传递file_names参数，保持输出格式与输入一致
    data_bs_save = np.clip(data_bs, 0, 255).astype(np.uint8)
    save_image_stack(data_bs_save, args.output_folder, prefix='bgsub', file_names=files)
    if args.out_npy:
        save_npy(data_bs, args.out_npy)

if __name__ == '__main__':
    main() 