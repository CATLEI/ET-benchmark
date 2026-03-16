import argparse
import numpy as np
from scipy.interpolate import interp1d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def axis_shift_align(data, angles, shift_range=20, numberOfSlices=5, show=False):
    Nx, Ny, Nz = data.shape
    shifts = (np.linspace(-shift_range, shift_range, 2*shift_range+1)).astype('int')
    # 选择总强度top 50%的slice
    tiltSeriesSum = np.sum(data, axis=(1, 2))
    temp = tiltSeriesSum.argsort()[Nx // 2:]
    slices = temp[np.random.permutation(temp.size)[:numberOfSlices]]
    print('Reconstruction slices:', slices)
    I = np.zeros(shifts.size)
    for i in range(shifts.size):
        shiftedTiltSeries = np.roll(data[slices, :, :], shifts[i], axis=1)
        for s in range(numberOfSlices):
            recon = wbp2(shiftedTiltSeries[s, :, :], angles, Ny, 'ramp', 'linear')
            I[i] = I[i] + np.amax(recon)
    best_shift = shifts[np.argmax(I)]
    print('最佳shift:', best_shift)
    result = np.roll(data, best_shift, axis=1)
    if show:
        idx = slices[0]
        plt.figure(figsize=(10,5))
        plt.subplot(1,2,1)
        plt.imshow(data[idx], cmap='gray')
        plt.title(f'原始 slice {idx}')
        plt.axis('off')
        plt.subplot(1,2,2)
        plt.imshow(result[idx], cmap='gray')
        plt.title(f'对齐后 slice {idx}, shift={best_shift}')
        plt.axis('off')
        plt.suptitle(f'最佳shift: {best_shift}')
        plt.tight_layout()
        plt.show()
    return result, best_shift

def wbp2(sinogram, angles, N=None, filter="ramp", interp="linear"):
    if sinogram.ndim != 2:
        raise ValueError('Sinogram must be 2D')
    (Nray, Nproj) = sinogram.shape
    # print("sinogram.shape:", sinogram.shape)
    # print("angles.size:", angles.size)
    if Nproj != angles.size:
        raise ValueError('Sinogram does not match angles!')
    interpolation_methods = ('linear', 'nearest', 'spline', 'cubic')
    if interp not in interpolation_methods:
        raise ValueError("Unknown interpolation: %s" % interp)
    if not N:
        N = int(np.floor(np.sqrt(Nray**2 / 2.0)))
    ang = np.double(angles) * np.pi / 180.0
    F = makeFilter(Nray, filter)
    s = np.lib.pad(sinogram, ((0, F.size - Nray), (0, 0)), 'constant', constant_values=(0, 0))
    s = np.fft.fft(s, axis=0) * F
    s = np.real(np.fft.ifft(s, axis=0))
    s = s[:Nray, :]
    recon = np.zeros((N, N))
    center_proj = Nray // 2
    [X, Y] = np.mgrid[0:N, 0:N]
    xpr = X - int(N) // 2
    ypr = Y - int(N) // 2
    for j in range(Nproj):
        t = ypr * np.cos(ang[j]) - xpr * np.sin(ang[j])
        x = np.arange(Nray) - center_proj
        if interp == 'linear':
            bp = np.interp(t, x, s[:, j], left=0, right=0)
        elif interp == 'spline':
            interpolant = interp1d(x, s[:, j], kind='slinear', bounds_error=False, fill_value=0)
            bp = interpolant(t)
        else:
            interpolant = interp1d(x, s[:, j], kind=interp, bounds_error=False, fill_value=0)
            bp = interpolant(t)
        recon = recon + bp
    recon = recon * np.pi / 2 / Nproj
    return recon

def makeFilter(Nray, filterMethod="ramp"):
    N2 = 2**np.ceil(np.log2(Nray))
    freq = np.fft.fftfreq(int(N2)).reshape(-1, 1)
    omega = 2 * np.pi * freq
    filter = 2 * np.abs(freq)
    if filterMethod == "ramp":
        pass
    elif filterMethod == "shepp-logan":
        filter[1:] = filter[1:] * np.sin(omega[1:]) / omega[1:]
    elif filterMethod == "cosine":
        filter[1:] = filter[1:] * np.cos(filter[1:])
    elif filterMethod == "hamming":
        filter[1:] = filter[1:] * (0.54 + 0.46 * np.cos(omega[1:] / 2))
    elif filterMethod == "hann":
        filter[1:] = filter[1:] * (1 + np.cos(omega[1:] / 2)) / 2
    elif filterMethod == "none":
        filter[:] = 1
    else:
        raise ValueError("Unknown filter: %s" % filterMethod)
    return filter

def main():
    from io_utils import load_image_stack, save_image_stack, save_npy, load_angles
    parser = argparse.ArgumentParser(description='自动tilt轴平移对齐')
    parser.add_argument('input_folder', help='输入图像文件夹')
    #parser.add_argument('angles_file', help='角度文件')
    parser.add_argument('--angles', default=None, help='角度文件（部分功能需要）')
    parser.add_argument('output_folder', help='输出图像文件夹')
    parser.add_argument('--out_npy', default=None, help='可选，保存为npy文件')
    parser.add_argument('--shift_range', type=int, default=20, help='最大平移范围')
    parser.add_argument('--num_slices', type=int, default=5, help='用于重建的切片数')
    parser.add_argument('--show', action='store_true', help='显示对比图')
    args = parser.parse_args()
    data, files = load_image_stack(args.input_folder)
    angles = load_angles(args.angles)
    result, best_shift = axis_shift_align(data, angles, shift_range=args.shift_range, numberOfSlices=args.num_slices, show=args.show)
    result_save = np.clip(result, 0, 255).astype(np.uint8)
    save_image_stack(result_save, args.output_folder, prefix='axis_shift_aligned',file_names=files)
    if args.out_npy:
        save_npy(result, args.out_npy)
    print(f'最佳shift: {best_shift}')

if __name__ == '__main__':
    main()
