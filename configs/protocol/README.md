# Protocol configs (batch)

Generate / refresh:

```bash
PYTHONPATH=. python scripts/generate_protocol_configs.py \
  --base configs/wbp_sirt_hybrid_aligned_model_sm70.yaml
```

This **removes** old single-condition `axis_w_sm*.yaml` / `axis_s_sm70_step*.yaml` /
`axis_ws_sm40_step*.yaml` and writes batch YAMLs only.

## Batch files

| File | Datasets | Purpose |
| --- | --- | --- |
| `axis_w_batch.yaml` | sm80…sm40 @ 1° | Axis W: tilt-range scan |
| `axis_s_batch.yaml` | sm70 @ 1° + step2 + step4 | Axis S: sparse views (1° is baseline) |
| `axis_ws_batch.yaml` | sm40 @ 2° | Interaction (±40°×2°, simulated) |
| `task_b_isonet_sm70.yaml` | sm70 only, IsoNet on | Track B |
| `task_c_wucon_sm70.yaml` | sm70 only, WUCON full volume | Track C |
| `task_c_deepdewedge_sm70.yaml` | sm70 only, DeepDeWedge on | Track C |

## Submit

```bash
et-dflow benchmark configs/protocol/axis_w_batch.yaml --output-dir ./results
et-dflow benchmark configs/protocol/axis_s_batch.yaml --output-dir ./results
et-dflow benchmark configs/protocol/axis_ws_batch.yaml --output-dir ./results
```

Hybrid flow: local prep per dataset → one remote pod per `(dataset, algorithm)` →
local eval. Results land under `results/<time>/data/<dataset_key>/<algorithm>/`.

Angles are read from each tilt series’ HyperSpy `TEM.tilt_series`. Algorithm-block
`tilt_range` is only a fallback (batch configs set it to the widest range in that file).

Optional shard if Bohrium concurrency is tight:

```yaml
benchmark_suite:
  max_datasets_per_workflow: 2
```

## Axis S and the 1° baseline

`axis_s_batch.yaml` **includes** `aligned_model_sm70` (1°) by default so the
step→metric curve has a baseline in the same run.

If you set that dataset `enabled: false` to avoid re-running the same stack as
Axis W, `report_protocol_tracks.py` on the Axis S run will only show 2°/4°. Join
the 1° metrics from the Axis W run directory when plotting the sparse curve.

## Protocol sidecar metrics

```bash
python scripts/reeval_protocol_metrics.py --run-dir results/<run> --tilt-min -70 --tilt-max 70
python scripts/report_protocol_tracks.py --run-dir results/<run>
```

For Axis W / WS batches, pass matching tilt limits when re-evaluating (or run
per-dataset). Wedge angle in metadata is `missing_wedge_deg = 180 − 2α`.
