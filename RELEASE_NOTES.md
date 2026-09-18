# Austin 911 response time — `v2026.09`

First release. A leakage-checked, time-split prediction dataset built from the City of Austin's
public `APD 911 Calls for Service 2023-2026` records: predict, **at the moment a call is
dispatched**, whether the first unit will reach the caller more than 20 minutes later.

**1,049,636 rows**, three time-separated splits, Public Domain source data. Repository is
**private**; this release becomes public only on explicit authorisation.

## Get it

```bash
git clone https://github.com/earino/austin-911-response.git
cd austin-911-response
python3 get_dataset.py --dest ./task       # downloads these assets and lays out the runner layout
python3 code/qualify_dataset.py ./task     # 33 qualification checks
sh baseline/reproduce_baseline.sh ./task   # the recorded baseline
```

## Assets

GitHub does not allow `/` in asset names, so these are flat; `get_dataset.py` restores the layout.

| asset | bytes | becomes |
|---|---|---|
| `train.csv` | 71,546,966 | `public/train.csv` |
| `eval.csv` | 35,801,537 | `public/eval.csv` |
| `holdout.csv` | 24,075,321 | `private/holdout.csv` |
| `meta.json` | 2,121 | `meta.json` |
| `quality.json` | 3,434 | `quality.json` |

Verify with `sha256sum -c SHA256SUMS`. Artifact version
`e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328`.

| split | period | rows | positives | rate |
|---|---|---|---|---|
| train | before 2025-01-01 | 572,180 | 231,025 | 0.403763 |
| eval | 2025 | 285,665 | 109,860 | 0.384576 |
| holdout | 2026-01-01 onward | 191,791 | 72,450 | 0.377755 |

The labelled holdout is included and is intended to be public once this repository is; it must
still stay out of an evaluated agent's workspace during a benchmark run.

## What was checked before this was released

- **Qualification gate 1.3.0: 33 checks, 0 failures**, on the worker over the full artifact —
  leakage, prediction timing, split capacity and boundary integrity, and the runner's input
  contract.
- **No leakage:** `response_time` (the label's source) is absent from every file; no shipped
  column separates the classes on its own; post-hoc columns are excluded and listed.
- **Splits are temporal and disjoint**, with both classes in eval and holdout.
- **Provenance:** row counts identical to the source's per-year counts, so extraction lost and
  duplicated nothing. Extraction cost 69 HTTP requests.

## Measured

| | |
|---|---|
| Baseline, single feature (`initial_problem_category`) | eval AUC **0.627031** |
| Baseline, the benchmark's own `train.py` unmodified | eval AUC **0.7691** |
| Same, re-scored through `validate.py`'s `predict_proba` | eval AUC **0.7691** |
| Baseline train / score time | 2.6 s / 0.3 s |
| Build + qualification | 353.7 s on 2 vCPU / 2 GB, ~136 MB output, 69 requests |
| Label-clock offset (2,000 rows) | median **−57 s**, p05 −206 s, p95 0 s, range −468 … +6,041 s |

Baselines are floors, not results. **No agent or harness comparison has been run** — a separate
milestone, and no comparison should be inferred.

## Known properties, stated rather than hidden

- `incident_number` is **not unique**: 24 of 1,049,636 rows share a number with another row
  (11 train / 7 eval / 6 holdout, each pair inside one split). **4 of those 24 pairs carry
  different labels** — different events sharing a number, hours apart, different category and
  sector. Declared in `quality.json`; no unique-entity claim is made.
- The label's clock starts ~57 s before the prediction instant on average (measured above).
- The source is a live catalogue, so rebuilding later will not reproduce these bytes. The hashes,
  not the source URL, define this version.
- Class balance (~38–40% positive) follows from the physical 20-minute threshold, which was
  deliberately not tuned to balance classes. The threshold search's ten probes are recorded in
  `README.md`.

## Two open decisions for the maintainer

1. **A licence for the published code** (`code/`) and for the three benchmark runner files in
   `baseline/`. The benchmark project carries no licence, so including its files here is the
   maintainer's call to confirm before this repository becomes public.
2. **Public visibility itself** — nothing is public yet, by instruction.

## Citation

> City of Austin. *APD 911 Calls for Service 2023-2026*. Austin Open Data. Public Domain.
> Accessed 2026-09-18. Derived dataset: Austin 911 response time prediction dataset, version
> 2026.09, artifact `e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328`.
