#!/usr/bin/env python3
"""Offline search for algorithms.*.parameters.output_to_gt (no image rebuild).

Enumerates axis permutations × flips (trim fixed) and ranks by NCC vs GT.
Paste the printed block into YAML under the algorithm's parameters.

Example::

    python scripts/calibrate_output_to_gt.py \\
      --recon results/<ts>/data/aligned_model_sm70/astra_sirt/reconstruction_native.hspy \\
      --gt data/datasets/simulated/aligned_model_sm70_v1/ground_truth/volume.hspy \\
      --trim leading --target-shape 512,512,512
"""

from __future__ import annotations

import argparse
import itertools
from typing import List, Sequence, Tuple

import hyperspy.api as hs
import numpy as np
import yaml

from et_dflow.domain.evaluation.volume_alignment import (
    apply_fixed_geometry,
    ncc,
    zscore,
)


def _load(path: str) -> np.ndarray:
    sig = hs.load(path)
    if isinstance(sig, list):
        sig = sig[0]
    return np.asarray(sig.data, dtype=np.float32)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recon", required=True, help="Native reconstruction .hspy")
    parser.add_argument("--gt", required=True, help="Ground-truth volume .hspy")
    parser.add_argument(
        "--trim",
        default="leading",
        choices=("leading", "trailing", "center"),
    )
    parser.add_argument(
        "--target-shape",
        default="512,512,512",
        help="Comma-separated Z,Y,X (default 512,512,512)",
    )
    parser.add_argument("--top", type=int, default=5, help="Print top-N candidates")
    args = parser.parse_args()

    target = tuple(int(x) for x in args.target_shape.split(","))
    if len(target) != 3:
        raise SystemExit("--target-shape must have 3 ints")

    recon = _load(args.recon)
    gt = _load(args.gt)
    if gt.shape != target:
        gt = apply_fixed_geometry(
            gt, target, axes_order=(0, 1, 2), flip_axes=[], trim="center"
        )
    gt_z = zscore(gt)

    perms = list(itertools.permutations((0, 1, 2)))
    flip_opts: List[Tuple[int, ...]] = []
    for mask in range(8):
        flips = tuple(i for i in range(3) if mask & (1 << i))
        flip_opts.append(flips)

    scored = []
    for order in perms:
        for flips in flip_opts:
            try:
                cand = apply_fixed_geometry(
                    recon,
                    target,
                    axes_order=order,
                    flip_axes=flips,
                    trim=args.trim,
                )
            except Exception:
                continue
            score = ncc(gt_z, zscore(cand))
            scored.append((score, list(order), list(flips)))

    scored.sort(key=lambda x: x[0], reverse=True)
    print(f"recon={args.recon}")
    print(f"gt={args.gt} target={target} trim={args.trim}")
    print(f"candidates={len(scored)}")
    for i, (score, order, flips) in enumerate(scored[: max(1, args.top)]):
        print(f"#{i+1} ncc={score:.6f} axes_order={order} flip_axes={flips}")

    best_score, best_order, best_flips = scored[0]
    block = {
        "output_to_gt": {
            "axes_order": best_order,
            "flip_axes": best_flips,
            "trim": args.trim,
            "target_shape": list(target),
        }
    }
    print("\n# Paste under algorithms.<name>.parameters:")
    print(yaml.safe_dump(block, sort_keys=False))
    print(f"# best ncc={best_score:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
