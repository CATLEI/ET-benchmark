"""
Convert TIFF (single file or stack) to HyperSpy .hspy and validate the output.

Usage example (Windows):
    python scripts/convert_tiff_to_hspy_validate.py ^
        --input "data\\test_dataset\\Ag-256-prism-align.tiff" ^
        --output "data\\test_dataset\\Ag-256-prism-align.hspy"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import hyperspy.api as hs

from et_dflow.infrastructure.data.converters.format_converter import tiff_to_hyperspy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TIFF -> .hspy converter with validation.")
    parser.add_argument(
        "--input",
        required=True,
        type=str,
        help="Path to input TIFF (.tif/.tiff). TIFF stack is supported.",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input TIFF not found: {input_path}")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix(".hspy")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("[convert] input :", input_path)
    print("[convert] output:", output_path)

    # 1) Convert
    signal = tiff_to_hyperspy(str(input_path), str(output_path))

    # 2) Report conversion result
    print("[convert] saved  :", output_path)
    print("[convert] shape  :", signal.data.shape)
    print("[convert] dtype  :", signal.data.dtype)

    # 3) Verify by reloading
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

