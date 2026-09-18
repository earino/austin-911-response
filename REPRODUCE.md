# Reproduce this version

Five things can be checked here, in increasing cost. **Nothing in this repository needs access
to any other repository.** The pinned revision of this package is the tag **`v2026.09`**;
`git rev-parse v2026.09` gives the exact commit if you need it.

```bash
git clone https://github.com/earino/austin-911-response.git
cd austin-911-response
```

## 0. Dependencies

The construction script and the qualification gate are **stdlib-only** (Python 3.13, no packages).
Only the baseline needs the benchmark's dependency ranges:

```
pandas>=2.2,<3     numpy>=1.26     xgboost>=3.0     scikit-learn>=1.5
```

The versions actually resolved in the recorded baseline run: Python 3.13.15, pandas 2.3.3,
numpy 2.5.3, xgboost 3.4.1, scikit-learn 1.9.1.

## 1. Download the dataset (required for everything below)

```bash
python3 get_dataset.py --dest ./task
```

The release assets are flat because GitHub does not allow `/` in asset names; the script restores
the runner's layout (`public/`, `private/`, `meta.json`, `quality.json`) and verifies every file
against `SHA256SUMS`. Needs a credential: `gh` already authenticated, or `GITHUB_TOKEN`. The
by-hand `gh release download` equivalent is in `README.md`.

## 2. Verify what you downloaded

```bash
cd task && cp ../SHA256SUMS . && sha256sum -c SHA256SUMS && cd ..
```

Covered files and their SHA-256 values are also in `MANIFEST.json`. The combined artifact version
is `e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328`.

## 3. Re-run the qualification gate

```bash
python3 code/qualify_dataset.py ./task
python3 code/qualify_dataset.py --selftest      # the gate must still reject its broken fixtures
```

The released version passed **33 checks, 0 failures** (gate version 1.3.0) over the full
artifact, executed on a worker. Two earlier builds failed and both failures were gate defects,
not data defects; the history is in the factory's record and summarised in `RELEASE_NOTES.md`.

## 4. Reproduce the baseline

```bash
sh baseline/reproduce_baseline.sh ./task
```

That script copies the benchmark's own `train.py`, `validate.py` and `validate.sh` from
`baseline/` (verbatim, hashes in `baseline/README.md` and `MANIFEST.json`), materializes
`task.json` and `data/{train,eval}.csv` exactly as the benchmark's `bench/workdir.py` does, then
runs both contract entry points. It never copies the private holdout into a workdir.

**Recorded result:**

| | |
|---|---|
| `train.py` eval AUC | **0.7691** |
| `validate.py` eval AUC (via `predict_proba`) | **0.7691** |
| `train.py` exit / `validate.sh` exit | 0 / 0 |
| `[validate] CONTRACT OK` | yes |
| train / score time | 2.6 s / 0.3 s |

Both figures agreeing is the point: `train.py` scores its own in-memory model, while
`validate.py` re-runs the file and scores through `predict_proba(df)` with the target column
removed — so the contract is satisfied, not merely the training script.

## 5. Rebuild the dataset from the source API

```bash
python3 code/build.py --out /tmp/extract \
    --built-at 2026-09-18T19:36:55.770697+00:00
```

**`--built-at` is required for a byte-identical rebuild**, because `meta.json` embeds the build
timestamp. The pin above is this release's recorded `built_at_utc` (`MANIFEST.json`). Without it
the three split files still match and `meta.json` does not — which is exactly how the first
attempt at reproducing this version failed verification while every data file was identical.

Then compare:

```bash
cd /tmp/extract && sha256sum -c /path/to/repo/SHA256SUMS
```

**Measured cost:** **69 HTTP requests** — 15 aggregate queries (1 row count, 10 threshold probes,
1 re-measure, 3 per-split counts) plus 54 page requests at 20,000 rows per page (29 train, 15
eval, 10 holdout) — and 353.7 s wall clock on a 2-vCPU / 2 GB machine, producing ~136 MB.

**Do not expect a byte-identical rebuild on a later date.** The source is a live catalogue the
City updates, so a rebuild after 2026-09-18 will include later rows and any revisions. This
version's identity is its hashes, not its source URL.

## Measuring the clock offset instead of assuming it

```bash
python3 code/measure_clock_offset.py 2000 --json
```

Reports the distribution of
`(first_unit_arrived_datetime - response_datetime) - response_time` over the first 2,000 rows in
`:id` order. Measured: median **−57 s**, mean −53.5 s, p05 −206 s, p95 0 s, range −468 s …
+6,041 s; 1,890 of 2,000 rows negative (the label's clock starts *earlier* than the prediction
instant), 55 exactly zero, 55 positive.

## What is deliberately not here

- **No agent or harness comparison.** This package contains one baseline through the runner's
  contract. Comparing coding agents or harnesses is a separate milestone and no result of that
  kind exists.
- **No synthetic stand-in for the benchmark.** The three runner files are the benchmark's own,
  copied verbatim and hash-checked; nothing here reimplements or approximates them.
