# ET-tomo Benchmark Protocol (frozen v1)

Status: **protocol document**. Core hybrid workflow, existing algorithm adapters
that already score on `aligned_model_sm70`, and the formulas behind current
`psnr` / `ssim` / `fsc_resolution_px` names are **not** changed by this protocol.
New conditions and scientific metrics are added beside the core path
(new configs, data-prep scripts, bypass re-eval / report scripts).

Scope: **materials electron tomography** — reconstruct a 3D volume from an
aligned single-axis tilt series. Not particle picking or subtomogram averaging.

## 1. Task tracks (do not share one leaderboard)

| Track | Question | Allowed methods | Do not mix with |
| --- | --- | --- | --- |
| **A** Projection → volume | Classical / iterative reconstruction from tilts | WBP, ASTRA FBP, ASTRA SIRT, TIGRE SIRT, CPU SIRT, GENFIRE, TVM | B, C, oracle-prior |
| **B** Post-recon wedge fill | Improve an existing tomogram | IsoNet (input = Track A volume) | A blind ranking |
| **C** Self-supervised from projections | Denoise + fill wedge from tilts | DeepDeWedge, WUCON | A-only ranking without wedge-in/out |
| **Oracle-prior** | Discrete recon with known gray levels | DART, TVR-DART (`dart_gray_levels` / `tvr_n_gray` from GT) | Blind Track A |

Primary metrics (chosen before looking at scores):

- **Track A:** intensity-affine-aligned SSIM and Pearson CC vs GT; morphology only for porous/particle samples with a fixed threshold rule.
- **Track B/C:** wedge-out CC (fidelity in measured Fourier region) and wedge-in CC (or wedge-in FSC). Global PSNR is diagnostic only.
- **Experimental (no GT):** held-out high-tilt reprojection error; directional resolution. Never PSNR. Never treat ±70° WBP/SIRT as GT (pseudo-reference only).

Diagnostic / secondary (never folded into a single score): wall-clock time, peak memory, full-volume flag, failure rate, seed, image tag.

## 2. Condition axes (plot separately)

Missing-wedge angle for single-axis ±α is **`180 − 2α`**. Config field
`missing_wedge_angle: 70` in historical YAML meant the **tilt limit**, not the
wedge. Reports must label tilt range and report wedge = `180 − 2α`.

### Axis W — tilt range (fixed 1° step)

Simulated, same GT (`model.tif`):

| Variant | Tilt range | Wedge | Native step |
| --- | --- | --- | --- |
| sm80 | ±80° | 20° | 1° |
| sm70 | ±70° | 40° | 1° |
| sm60 | ±60° | 60° | 1° |
| sm50 | ±50° | 80° | 1° |
| sm40 | ±40° | 100° | 1° |

`sm80`–`sm50` come from `scripts/convert_aligned_model_to_etdflow.py`. If no
independent ±40° stack exists, crop `|θ| ≤ 40°` from `sm80` **keeping 1°**
(`scripts/prepare_tilt_conditions.py`).

### Axis S — sparse views (fixed ±70°)

From the native 1° sm70 stack (~141 frames, −70…+70 inclusive):

| Step | Keep ends | Approx. frames |
| --- | --- | --- |
| 1° | all | 141 |
| 2° | −70, −68, …, +70 | 71 |
| 4° | −70, −66, …, +70 | 36 |

No angle interpolation. No extra noise when subsampling. Caption:
“per-frame dose fixed; frame count reduced” if projections are noisy.
Skipped angles are reprojection diagnostics only; GT remains the volume.

### Round-1 grid (confirmed)

- Axis W: five ranges at **1° only**.
- Axis S: **1° / 2° / 4°** only at ±70° (2°/4° from native TIFF stacks under `raw_data/`).
- One interaction point: **±40° × 2°** (~41 frames; simulated crop+sparse, **not** in-situ experiment). ±40°×4° (~21 frames) is excluded as too sparse.
- Full 5×3 grid is out of scope for round 1.
- Axis D (dose / noise) deferred.

### Experimental subset

From an aligned experimental series (~±70°): crop to ±60 / ±50 / ±40 using the
**same** alignment as the full series. Cannot invent ±80°. Held-out high tilts
are the reprojection test set. Experimental sparse 2°/4° is later and never
joined with simulated GT scores.

## 3. Intensity and Fourier protocol (bypass metrics)

Existing workflow metrics (`psnr`, `ssim`, …) stay as-is for continuity.

Bypass script `scripts/reeval_protocol_metrics.py` writes **new keys**:

- `protocol_affine_ssim`, `protocol_affine_cc`
- `protocol_wedge_out_cc`, `protocol_wedge_in_cc`
- `protocol_fsc_curve`, `protocol_fsc_res_0p5_px`, `protocol_fsc_res_0p143_px`
- optional `protocol_pixel_size_nm` when metadata provides it

Affine intensity fit is OLS of recon vs GT before SSIM/CC. Wedge masks use the
tilt axis and missing-wedge geometry from the dataset metadata.

## 4. Reporting

`scripts/report_protocol_tracks.py` reads an existing run directory and emits a
**separate** HTML with Track A / B / C / oracle-prior tables. It does not replace
`comparison_report.html` from the workflow. Percolation mismatch that is all
zeros is marked “non-discriminative” and excluded from “best” tags.

## 5. Algorithm parameter budgets (protocol configs)

Smoke configs in `configs/wbp_sirt_hybrid_aligned_model_sm70.yaml` remain
unchanged. Protocol runs use **copied** YAMLs under `configs/protocol/` with:

- Track A algorithms: same parameters as the sm70 hybrid config that already
  finished (do not retune after seeing scores).
- IsoNet (Track B): full pipeline; document real `isonet_pixel_size` for the
  material volume (default 10 Å is a cryo-ET habit, not a materials claim).
- WUCON (Track C): `wucon_recon_subset: false` for official tables; subset mode
  is smoke only.

## 6. Core-path freeze

Do not modify for protocol work:

- `et_dflow/infrastructure/workflows/baseline_workflow.py` and shared OPs
- Scoring adapters for WBP / ASTRA / TIGRE / TVM / GENFIRE / DeepDeWedge
- Formulas behind existing metric **names** in `chain.py`
- Algorithm blocks inside `configs/wbp_sirt_hybrid_aligned_model_sm70.yaml`

Allowed: new YAMLs, `scripts/prepare_tilt_conditions.py`, bypass metric module +
CLI, track report CLI, IsoNet/WUCON-only adapter/Dockerfile fixes.

## 7. References

- Weber et al., *Essential guidelines for computational method benchmarking*,
  Genome Biology (2019).
- DeepDeWedge, Nat Commun (2024) — CC, wedge-out CC, 0.143-FSC in/out wedge.
- IsoNet, Nat Commun (2022) — post-recon isotropic fill, 3D FSC anisotropy.
- WUCON, IJMS (2024) — unsupervised coordinate networks from projections.
