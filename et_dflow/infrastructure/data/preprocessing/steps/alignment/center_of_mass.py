import argparse
import numpy as np

def center_of_mass_align(data):
    """
    基于质心法对齐投影序列。
    """
    tiltSeries = data.astype(float)
    Nproj = tiltSeries.shape[2]
    offsets = np.zeros((Nproj, 2))
    for i in range(Nproj):
        offsets[i, :], tiltSeries[:, :, i] = centerOfMassAlign(tiltSeries[:, :, i])
    return tiltSeries, offsets

def centerOfMassAlign(image):
    (Nx, Ny) = image.shape
    y = np.linspace(0, Ny - 1, Ny)
    x = np.linspace(0, Nx - 1, Nx)
    [X, Y] = np.meshgrid(x, y, indexing="ij")
    if np.sum(image) == 0:
        return (0, 0), image
    imageCOM_x = int(np.sum(image * X) / np.sum(image))
    imageCOM_y = int(np.sum(image * Y) / np.sum(image))
    sx = -(imageCOM_x - Nx // 2)
    sy = -(imageCOM_y - Ny // 2)
    output = np.roll(image, sx, axis=0)
    output = np.roll(output, sy, axis=1)
    return (sx, sy), output

def main():
    from io_utils import load_image_stack, save_image_stack, save_npy
    parser = argparse.ArgumentParser(description='批量质心对齐')
    parser.add_argument('input_folder', help='输入图像文件夹')
    parser.add_argument('output_folder', help='输出图像文件夹')
    parser.add_argument('--out_npy', default=None, help='可选，保存为npy文件')
    parser.add_argument('--out_offsets', default=None, help='可选，保存平移参数npy')
    args = parser.parse_args()
    data, files = load_image_stack(args.input_folder)
    aligned, offsets = center_of_mass_align(data)
    # 修正：保存前clip并转uint8
    aligned_save = np.clip(aligned, 0, 255).astype(np.uint8)
    save_image_stack(aligned_save, args.output_folder, prefix='mass_aligned',file_names=files)
    if args.out_npy:
        save_npy(aligned, args.out_npy)
    if args.out_offsets:
        save_npy(offsets, args.out_offsets)

if __name__ == '__main__':
    main() 