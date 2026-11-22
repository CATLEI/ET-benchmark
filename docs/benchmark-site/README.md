# ET-tomo Benchmark Suite (static site)

Single-page leaderboard with Home / Leaderboard / Explorer / Datasets / Methods.
Dark and light themes (Hyper-Tomo palette). No separate Downloads section —
CSV export is inline on Leaderboard and Explorer; `data/cohorts.json` is linked
from Methods.

## View locally

`fetch` needs HTTP (not `file://`):

```bash
cd docs/benchmark-site
python3 -m http.server 8765
# open http://127.0.0.1:8765/
```

## Refresh data

```bash
PYTHONPATH=. python scripts/export_leaderboard_site.py \
  --run-dir results/aligned-model-sm70 \
  --run-dir results/aligned-model-sm70-20261110 \
  --run-dir results/aligned-model-sm70-20261111 \
  --run-dir results/aligned-model-sm70-isonet \
  --datasets-root data/datasets \
  --output docs/benchmark-site/data/cohorts.json
```

Datasets page sample cards (aligned_model, CeO₂, RESIRE vesicle / coral / Ta)
come from `metadata.yaml` under `--datasets-root`, not from run dirs.

Rows without `protocol_*` keys stay `legacy`; the UI shows an unaudited banner
and does not tag **best** on diagnostic columns.
