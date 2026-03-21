"""
Convert NumPy .npy (2D/3D/4D array, e.g. tomographic reconstruction volume) to HyperSpy .hspy
and validate by reloading.

Typical 3D reconstruction: shape (Z, Y, X) -> Signal3D if available (HyperSpy 1.x),
else BaseSignal (HyperSpy 2.x removed Signal3D in many builds).

Usage example (Windows):
    python scripts/convert_npy_to_hspy_validate.py ^
        --input "path\\to\\reconstruction.npy" ^
        --output "path\\to\\reconstruction.hspy"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import hyperspy.api as hs


def _array_to_signal(data: np.ndarray):
    """Map ndarray to an appropriate HyperSpy signal type.

    HyperSpy 2.x often exposes BaseSignal only for 3D+; Signal3D may be absent
    (AttributeError: module 'hyperspy.signals' has no attribute 'Signal3D').
    """
    sigs = hs.signals
    if data.ndim == 1:
        cls = getattr(sigs, "Signal1D", None)
        return cls(data) if cls is not None else sigs.BaseSignal(data)
    if data.ndim == 2:
        cls = getattr(sigs, "Signal2D", None)
        return cls(data) if cls is not None else sigs.BaseSignal(data)
    if data.ndim == 3:
        cls = getattr(sigs, "Signal3D", None)
        return cls(data) if cls is not None else sigs.BaseSignal(data)
    # 4D+ (e.g. batch, multi-channel)
    return sigs.BaseSignal(data)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="NumPy .npy -> .hspy converter with validation (2D/3D/4D+ arrays)."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=str,
        help="Path to input .npy file (single ndarray).",
    )
    parser.add_argument(
        "--output",
        default=None,
        type=str,
        help="Output .hspy path. If omitted, uses input stem + '.hspy' next to input.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip reload verification after saving.",
    )
    parser.add_argument(
        "--allow-pickle",
        action="store_true",
        help="Pass allow_pickle=True to np.load (only if your .npy requires it; security risk).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input .npy not found: {input_path}")
    if input_path.suffix.lower() != ".npy":
        raise ValueError(f"Expected .npy extension, got: {input_path.suffix}")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".hspy")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("[convert] input :", input_path)
    print("[convert] output:", output_path)

    load_kw = {"allow_pickle": bool(args.allow_pickle)}
    data = np.load(str(input_path), **load_kw)
    if not isinstance(data, np.ndarray):
        raise TypeError(
            f"Loaded object is not a numpy ndarray (got {type(data)}). "
            "This script expects a single array in the .npy file."
        )

    signal = _array_to_signal(data)
    signal.metadata.set_item("original_format", "npy")
    signal.metadata.set_item("original_file", str(input_path.resolve()))
    signal.save(str(output_path))

    print("[convert] saved  :", output_path)
    print("[convert] shape  :", signal.data.shape)
    print("[convert] dtype  :", signal.data.dtype)

    if not args.no_verify:
        reloaded = hs.load(str(output_path))
        print("[verify] reload shape:", reloaded.data.shape)
        print("[verify] reload dtype:", reloaded.data.dtype)

        if reloaded.data.shape != signal.data.shape:
            raise RuntimeError(
                "Verification failed: shape mismatch "
                f"(converted={signal.data.shape}, reloaded={reloaded.data.shape})"
            )
        if reloaded.data.dtype != signal.data.dtype:
            raise RuntimeError(
                "Verification failed: dtype mismatch "
                f"(converted={signal.data.dtype}, reloaded={reloaded.data.dtype})"
            )

        print("[ok] hspy file is valid and verification passed.")


if __name__ == "__main__":
    main()
