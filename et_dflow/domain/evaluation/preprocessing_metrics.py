from typing import Dict, Any, Optional
import numpy as np

def alignment_shift_stability(signal, _params=None):
    if signal is None or not hasattr(signal, "data"):
        return float("nan")
    data = np.asarray(signal.data)
    if data.ndim != 3 or data.shape[0] < 2:
        return float("nan")
    diffs = np.abs(np.diff(data, axis=0))
    return 1.0 / (1.0 + float(np.mean(diffs)))

def alignment_cross_correlation_peak(signal, _params=None):
    if signal is None or not hasattr(signal, "data"):
        return float("nan")
    data = np.asarray(signal.data)
    if data.ndim != 3 or data.shape[0] < 2:
        return 1.0
    from scipy.signal import correlate2d
    ref = data[0]
    peaks = [float(np.max(correlate2d(ref, data[i], mode="same"))) for i in range(1, data.shape[0])]
    return float(np.mean(peaks)) if peaks else 1.0

def denoising_snr_estimate(signal, _params=None):
    if signal is None or not hasattr(signal, "data"):
        return float("nan")
    data = np.asarray(signal.data)
    if data.size == 0:
        return float("nan")
    s = float(np.std(data))
    return float(np.mean(data)) / s if s > 0 else 0.0

def denoising_local_variance(signal, _params=None):
    if signal is None or not hasattr(signal, "data"):
        return float("nan")
    data = np.asarray(signal.data)
    if data.ndim == 3:
        data = data.mean(axis=0)
    from scipy.ndimage import uniform_filter
    lm = uniform_filter(data, size=3)
    lv = uniform_filter(data ** 2, size=3) - lm ** 2
    return float(np.nanmean(lv))

ALIGNMENT_METRICS = {"shift_stability": alignment_shift_stability, "cross_correlation_peak": alignment_cross_correlation_peak}
DENOISING_METRICS = {"snr_estimate": denoising_snr_estimate, "local_variance": denoising_local_variance}

def compute_alignment_metrics(path, alignment_metrics=None, before_alignment_path=None):
    import hyperspy.api as hs
    alignment_metrics = alignment_metrics or list(ALIGNMENT_METRICS.keys())
    signal = hs.load(path)
    if isinstance(signal, list):
        signal = signal[0]
    return {n: (ALIGNMENT_METRICS[n](signal, {}) if n in ALIGNMENT_METRICS else None) for n in alignment_metrics}

def compute_denoising_metrics(path, denoising_metrics=None, before_denoising_path=None):
    import hyperspy.api as hs
    denoising_metrics = denoising_metrics or list(DENOISING_METRICS.keys())
    signal = hs.load(path)
    if isinstance(signal, list):
        signal = signal[0]
    return {n: (DENOISING_METRICS[n](signal, {}) if n in DENOISING_METRICS else None) for n in denoising_metrics}
