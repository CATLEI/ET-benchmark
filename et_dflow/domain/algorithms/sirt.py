"""
SIRT (Simultaneous Iterative Reconstruction Technique) algorithm for ET.

Contains core sirt_reconstruct and SIRT class, plus SIRTAlgorithm adapter for et_dflow.
"""

import numpy as np
import scipy.sparse as ss
from typing import Dict, Any

import hyperspy.api as hs

from et_dflow.domain.algorithms.base import Algorithm
from et_dflow.core.exceptions import AlgorithmError

def rmepsilon(input):
    if (np.size(input) > 1):
        input[np.abs(input) < 1e-10] = 0
    else:
        if np.abs(input) < 1e-10:
            input = 0
    return input

def calc_Nupdates(Nupdates, Niter):
    if Nupdates == 0:
        Nupdates = 0
    elif Nupdates == 100:
        Nupdates = 1
    else:
        Nupdates = int(round((Niter*(1 - Nupdates/100))))
    return Nupdates

def parallelRay(Nside, pixelWidth, angles, Nray, rayWidth):
    np.seterr(all='ignore')
    Nproj = angles.size
    offsets = np.linspace(-(Nray * 1.0 - 1) / 2, (Nray * 1.0 - 1) / 2, Nray) * rayWidth
    xgrid = np.linspace(-Nside * 0.5, Nside * 0.5, Nside + 1) * pixelWidth
    ygrid = np.linspace(-Nside * 0.5, Nside * 0.5, Nside + 1) * pixelWidth
    rows = np.zeros((2 * Nside * Nproj * Nray), dtype=np.float32)
    cols = np.zeros((2 * Nside * Nproj * Nray), dtype=np.float32)
    vals = np.zeros((2 * Nside * Nproj * Nray), dtype=np.float32)
    idxend = 0
    for i in range(0, Nproj):
        ang = angles[i] * np.pi / 180.
        xrayRotated = np.cos(ang) * offsets
        yrayRotated = np.sin(ang) * offsets
        xrayRotated[np.abs(xrayRotated) < 1e-8] = 0
        yrayRotated[np.abs(yrayRotated) < 1e-8] = 0
        a = -np.sin(ang)
        a = rmepsilon(a)
        b = np.cos(ang)
        b = rmepsilon(b)
        for j in range(0, Nray):
            t_xgrid = (xgrid - xrayRotated[j]) / a
            y_xgrid = b * t_xgrid + yrayRotated[j]
            t_ygrid = (ygrid - yrayRotated[j]) / b
            x_ygrid = a * t_ygrid + xrayRotated[j]
            t_grid = np.append(t_xgrid, t_ygrid)
            xx = np.append(xgrid, x_ygrid)
            yy = np.append(y_xgrid, ygrid)
            I = np.argsort(t_grid)
            xx = xx[I]
            yy = yy[I]
            Ix = np.logical_and(xx >= -Nside / 2.0 * pixelWidth, xx <= Nside / 2.0 * pixelWidth)
            Iy = np.logical_and(yy >= -Nside / 2.0 * pixelWidth, yy <= Nside / 2.0 * pixelWidth)
            I = np.logical_and(Ix, Iy)
            xx = xx[I]
            yy = yy[I]
            if (xx.size != 0 and yy.size != 0):
                I = np.logical_and(np.abs(np.diff(xx)) <= 1e-8, np.abs(np.diff(yy)) <= 1e-8)
                I2 = np.zeros(I.size + 1)
                I2[0:-1] = I
                xx = xx[np.logical_not(I2)]
                yy = yy[np.logical_not(I2)]
                length = np.sqrt(np.diff(xx)**2 + np.diff(yy)**2)
                numvals = length.size
                check1 = np.logical_and(b == 0, np.absolute(yrayRotated[j] - Nside / 2 * pixelWidth) < 1e-15)
                check2 = np.logical_and(a == 0, np.absolute(xrayRotated[j] - Nside / 2 * pixelWidth) < 1e-15)
                check = np.logical_not(np.logical_or(check1, check2))
                if np.logical_and(numvals > 0, check):
                    midpoints_x = rmepsilon(0.5 * (xx[0:-1] + xx[1:]))
                    midpoints_y = rmepsilon(0.5 * (yy[0:-1] + yy[1:]))
                    pixelIndicex = (np.floor(Nside / 2.0 - midpoints_y / pixelWidth)) * Nside + (np.floor(midpoints_x / pixelWidth + Nside / 2.0))
                    idxstart = idxend
                    idxend = idxstart + numvals
                    idx = np.arange(idxstart, idxend)
                    rows[idx] = i * Nray + j
                    cols[idx] = pixelIndicex
                    vals[idx] = length
            else:
                pass
    rows = rows[:idxend]
    cols = cols[:idxend]
    vals = vals[:idxend]
    A = ss.coo_matrix((vals, (rows, cols)), shape=(Nray * Nproj, Nside**2), dtype=np.float32)
    return A

class SIRT:
    def __init__(self, A, method, Nslice):
        self.A = A
        self.method = method
        (self.Nrow, self.Ncol) = self.A.shape
        self.f = np.zeros(self.Ncol, dtype=np.float32)
    def initialize(self):
        if self.method == 'landweber':
            self.AT = self.A.transpose()
        elif self.method == 'cimmino':
            self.A = self.A.tocsr()
            self.AT = self.A.transpose()
            rowInnerProduct = np.zeros(self.Nrow, dtype=np.float32)
            self.a = np.zeros(self.Ncol, dtype=np.float32)
            row = np.zeros(self.Ncol, dtype=np.float32)
            for i in range(self.Nrow):
                row[:] = self.A[i, :].toarray()
                rowInnerProduct[i] = np.dot(row, row)
            self.M = ss.diags(1/rowInnerProduct)
        elif self.method == 'component averaging':
            self.A = self.A.tocsr()
            self.AT = self.A.transpose()
            weightedRowProduct = np.zeros(self.Nrow, dtype=np.float32)
            self.a = np.zeros(self.Ncol, dtype=np.float32)
            s = np.zeros(self.Ncol, dtype=np.float32)
            for i in range(self.Ncol):
                s[i] = self.A[:, i].count_nonzero()
            row = np.zeros(self.Ncol)
            for i in range(self.Nrow):
                row[:] = self.A[i, :].toarray()
                weightedRowProduct[i] = np.sum(row * row * s)
            self.M = ss.diags(1/weightedRowProduct)
        else:
            print("Invalid update method!")
    def recon2(self, b, x, stepSize, index):
        self.f[:] = x
        if self.method == 'landweber':
            a = self.AT.dot(b - self.A.dot(self.f))
            self.f = self.f + a * stepSize
        elif self.method == 'cimmino':
            self.a[:] = 0
            g = self.M.dot(b - self.A.dot(self.f))
            self.a = self.AT.dot(g)
            self.f = self.f + self.a * stepSize / self.Nrow
        elif self.method == 'component averaging':
            self.a[:] = 0
            g = self.M.dot(b - self.A.dot(self.f))
            self.a = self.AT.dot(g)
            self.f = self.f + self.a * stepSize
        else:
            print("Invalid update method!")
        return self.f

def sirt_reconstruct(data, angles, Niter=10, stepSize=0.1, update_method='landweber'):
    update_methods = ('landweber', 'cimmino', 'component averaging')
    if update_method not in update_methods:
        raise ValueError(f'update_method must be one of {update_methods}')
    
    print(f"输入数据形状: {data.shape}")
    print(f"角度数量: {angles.size}")
    
    # 修正：确保数据格式正确
    # 对于SIRT重建，我们需要理解：
    # - 输入数据是投影图像 (H, W, Nproj)
    # - 每个投影图像对应一个角度
    # - 我们需要重建的是 (H, W) 的切片
    # - 所以Nslice = H，Nray = W
    
    if len(data.shape) == 3:
        # 输入是 (H, W, Nproj)
        H, W, Nproj = data.shape
        if Nproj == angles.size:
            print(f"数据格式: 高度={H}, 宽度={W}, 投影数={Nproj}")
            # 对于SIRT，我们重建每个高度位置的一个切片
            # 所以Nslice = H, Nray = W
            tiltSeries = data  # 保持 (H, W, Nproj) 格式
        else:
            raise ValueError(f"投影数量 {Nproj} 与角度数量 {angles.size} 不匹配")
    else:
        raise ValueError("输入数据必须是3维")
    
    Nslice, Nray, Nproj = tiltSeries.shape
    print(f"处理后数据形状: {tiltSeries.shape}, 角度数量: {angles.size}")
    
    # 数据预处理
    tiltAngles = angles.copy()
    if np.count_nonzero(tiltAngles) < tiltAngles.size:
        tiltAngles = tiltAngles + 0.001
    
    # 确保数据非负并保持原始范围
    if np.any(tiltSeries < 0):
        tiltSeries -= np.amin(tiltSeries)
    
    # 不要过度归一化，保持原始数据范围
    print(f"原始数据范围: min={tiltSeries.min():.6f}, max={tiltSeries.max():.6f}")
    
    # 创建投影矩阵：A的形状是 (Nray * Nproj, Nray * Nray)
    # 其中 Nray * Nproj 是投影数据的总数，Nray * Nray 是重建图像的总像素数
    A = parallelRay(Nray, 1.0, tiltAngles, Nray, 1.0)
    print(f"投影矩阵A形状: {A.shape}")
    
    # 重建结果：每个切片是 (Nray, Nray)
    recon = np.zeros([Nslice, Nray, Nray], dtype=np.float32, order='F')
    
    print("In sirt_reconstruct:")
    print("  tiltAngles.shape:", tiltAngles.shape)
    print("  tiltSeries.shape:", tiltSeries.shape)
    print("  Nslice:", Nslice)
    print("  Nray:", Nray)
    print("  Nproj:", Nproj)
    print("  stepSize:", stepSize)
    
    r = SIRT(A, update_method, Nslice)
    r.initialize()
    
    for i in range(Niter):
        for s in range(Nslice):
            # 取第s个高度位置的投影数据
            b = tiltSeries[s, :, :].transpose().flatten()  # (Nproj, Nray) -> (Nray * Nproj,)
            recon_slice = recon[s, :, :].flatten()  # (Nray, Nray) -> (Nray * Nray,)
            recon[s, :, :] = r.recon2(b, recon_slice, stepSize, s).reshape((Nray, Nray))
        recon[recon < 0] = 0
        
        # 添加调试信息
        if i == 0 or i == Niter - 1:
            print(f"第 {i} 轮迭代 - 重建数据范围: min={recon.min():.6f}, max={recon.max():.6f}")
            print(f"  非零像素数量: {np.count_nonzero(recon)}")
            print(f"  数据均值: {recon.mean():.6f}")
        else:
            print(f"第 {i} 轮迭代已完成")
    
    print(f"重建完成，数据范围: min={recon.min():.6f}, max={recon.max():.6f}")
    return recon


class SIRTAlgorithm(Algorithm):
    """
    SIRT (Simultaneous Iterative Reconstruction Technique) adapter for et_dflow.

    Wraps sirt_reconstruct for use with Hyperspy Signal2D tilt series and
    dflow workflow (--input, --output, --config).
    """

    def __init__(self, name: str = "sirt", config: Dict[str, Any] = None):
        default_config = {
            "iterations": 30,
            "relaxation_factor": 0.5,
            "update_method": "landweber",
        }
        if config:
            default_config.update(config)
        super().__init__(name, default_config)

    def _get_tilt_angles(
        self, data: hs.signals.Signal2D, config: Dict[str, Any]
    ) -> np.ndarray:
        """Get tilt angles from config or data metadata (same logic as WBP)."""
        if "tilt_angles" in config:
            angles = config["tilt_angles"]
            if isinstance(angles, (list, np.ndarray)):
                return np.array(angles, dtype=np.float64)
        try:
            if hasattr(data.metadata, "Acquisition_instrument"):
                tem = getattr(data.metadata.Acquisition_instrument, "TEM", None)
                if tem and hasattr(tem, "tilt_series"):
                    tilt_angles = tem.tilt_series
                    if tilt_angles is not None:
                        return np.array(tilt_angles, dtype=np.float64)
        except (AttributeError, TypeError):
            pass
        n_tilts = data.data.shape[0]
        tilt_range = config.get("tilt_range", [-60, 60])
        return np.linspace(tilt_range[0], tilt_range[1], n_tilts)

    def _execute(
        self,
        data: hs.signals.Signal2D,
        config: Dict[str, Any],
    ) -> hs.signals.Signal2D:
        """
        Execute SIRT reconstruction.

        Args:
            data: Tilt series Signal2D, shape (n_tilts, height, width).
            config: Algorithm config (iterations, relaxation_factor, update_method, etc.).

        Returns:
            3D reconstruction as Signal2D (navigation Z, signal Y/X).
        """
        if data.data.ndim != 3:
            raise AlgorithmError(
                "SIRT expects 3D tilt series (n_tilts, height, width)",
                details={"algorithm": "sirt", "ndim": data.data.ndim},
            )
        n_tilts, height, width = data.data.shape
        angles = self._get_tilt_angles(data, config)
        if angles.size != n_tilts:
            raise AlgorithmError(
                f"Tilt angles count {angles.size} does not match n_tilts {n_tilts}",
                details={"algorithm": "sirt"},
            )
        # sirt_reconstruct expects (Nslice, Nray, Nproj) = (height, width, n_tilts)
        tilt_series = np.transpose(data.data, (1, 2, 0)).astype(np.float32)
        iterations = config.get("iterations", 30)
        step_size = config.get("relaxation_factor", 0.5)
        update_method = config.get("update_method", "landweber")
        try:
            recon = sirt_reconstruct(
                tilt_series,
                angles,
                Niter=iterations,
                stepSize=step_size,
                update_method=update_method,
            )
        except Exception as e:
            raise AlgorithmError(
                f"SIRT reconstruction failed: {e}",
                details={"algorithm": "sirt", "error": str(e)},
            ) from e
        # recon shape (Nslice, Nray, Nray) -> Hyperspy Signal2D
        result_signal = hs.signals.Signal2D(recon)
        result_signal.metadata.set_item("General.title", "SIRT Reconstruction")
        result_signal.metadata.set_item("Signal.quantity", "Intensity")
        try:
            if result_signal.axes_manager:
                if result_signal.axes_manager.navigation_dimension > 0:
                    nav_axis = result_signal.axes_manager.navigation_axes[0]
                    nav_axis.name = "Z"
                    nav_axis.units = "px"
                if result_signal.axes_manager.signal_dimension >= 2:
                    sig_axes = result_signal.axes_manager.signal_axes
                    sig_axes[0].name = "Y"
                    sig_axes[0].units = "px"
                    sig_axes[1].name = "X"
                    sig_axes[1].units = "px"
        except (AttributeError, IndexError, TypeError):
            pass
        return result_signal 