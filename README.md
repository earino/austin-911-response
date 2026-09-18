# Austin 911 response time — prediction dataset

A leakage-checked, time-split prediction dataset built from the City of Austin's public
`APD 911 Calls for Service 2023-2026` records. The task is to predict, **at the moment a call is
dispatched**, whether the first police unit will reach the caller later than a fixed threshold.

- **Version:** `2026.09` — artifact version `e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328`
- **Rows:** 1,049,636 across three time-separated splits
- **Source licence:** Public Domain (City of Austin)
- **Status:** private, prepared for review. No agent or harness comparison has been run.

Everything needed to verify, rebuild and evaluate this dataset is in this repository: the
construction script, the qualification gate, the runner used for the baseline, and the download
tooling. **No access to any other repository is required.**

## Quick start

```bash
git clone https://github.com/earino/austin-911-response.git
cd austin-911-response
python3 get_dataset.py --dest ./task      # downloads the release assets into the runner layout
python3 code/qualify_dataset.py ./task    # re-runs all 33 qualification checks
sh baseline/reproduce_baseline.sh ./task  # reproduces the recorded baseline
```

`get_dataset.py` needs a credential because this repository is private: either the `gh` CLI,
already authenticated, or `GITHUB_TOKEN` in the environment.

---

## Task

**Prediction question.** For a dispatched Austin police 911 call, will a patrol unit reach the
caller more than 20 minutes after the call was dispatched?

**Unit of observation.** One row is one dispatched call record from the source catalogue.

**Target.** `late` — a 0/1 column derived from the portal's own `response_time` field, an integer
number of seconds:

```
late = 1  if  response_time > 1200     # 1200 s = 20 minutes
```

**Prediction time.** The moment the 911 call-taker's dispatch screen opens, recorded as
`response_datetime`. Everything a model may use must be known at that instant. `response_time` —
the source of the label — is **never shipped in any split file**.

**Population and dates.** Every row the catalogue returns within the dataset's own coverage,
2023-01-01 through 2026-09-18 (the extraction date), except rows whose `response_time` is null:
those cannot be labelled, and the extraction query excludes them (`response_time IS NOT NULL`).
Measured: **0 rows** in the three shipped windows were dropped after retrieval.

**What the outcome means in practice.** A positive row is a call where the caller waited more
than 20 minutes for a unit to arrive. The dataset is useful for asking which *dispatch-time*
signal — call type, sector, hour of day, free-text problem description — carries information
about that wait. It is not a model of demand, of unit availability, or of whether the response
was appropriate.

### How the 20-minute threshold was chosen

Fixed by binary search over the **training window only**, before any row was scored, so that the
training positive rate sits just at or above 0.40. The search's ten probes are recorded in the
extract's own `manifest.json`:

| T (s) | rows above | rate | | T (s) | rows above | rate |
|---|---|---|---|---|---|---|
| 10800 | 26,590 | 0.0465 | | 960 | 270,820 | 0.4733 |
| 5400 | 64,869 | 0.1134 | | 1140 | 239,627 | 0.4188 |
| 2700 | 125,867 | 0.2200 | | **1200** | **231,025** | **0.4038** |
| 1320 | 215,808 | 0.3772 | | 1260 | 223,179 | 0.3901 |
| 660 | 349,894 | 0.6115 | | 1200 (re-measured) | 231,025 | 0.4038 |

The rule is "the largest tested value whose training rate is still at or above the target", which
keeps the choice monotone and reproducible. 1260 s falls below 0.40 (0.3901), so **T = 1200 s**.
Measured training rate **0.403763** against a target of 0.40. Over the full series the rate is
lower (0.377755 in the holdout window), so the threshold is not a quantile that moves with the
data — it is one physical cut, chosen once and frozen.

## Source and permissions

| | |
|---|---|
| Source | Austin Open Data — *APD 911 Calls for Service 2023-2026* |
| Landing page | https://datahub.austintexas.gov/d/e687-fx2y |
| API | https://datahub.austintexas.gov/resource/e687-fx2y.json |
| Dataset id | `e687-fx2y` |
| Owner | City of Austin (Austin Police Department) |
| Access | anonymous Socrata API, no key, offset-paginated; verified live 2026-09-18 |
| Accessed | 2026-09-18 |
| **Data licence** | **Public Domain** |
| Construction code | see `LICENSE.md` — still an open decision, stated there rather than assumed |

**Licence evidence, quoted from the source rather than asserted:**

- The Socrata catalogue entry for `e687-fx2y` reports `license = "Public Domain"` (catalogue API
  v1, queried 2026-09-18).
- Re-confirmed the same day from `GET https://datahub.austintexas.gov/api/views/e687-fx2y.json`,
  which returns `"license": {"name": "Public Domain"}` for the view *APD 911 Calls for Service
  2023-2026*.

Redistribution of the source data is therefore permitted. Attribution to the City of Austin is
given here and in `LICENSE.md` regardless.

**Transformations applied.** Row selection (the catalogue's coverage within the split windows,
minus unlabelled rows), a derived binary label, and a temporal partition into three splits. No
row is edited, imputed, reweighted or synthesised, and no source field is recoded except the
label. Column exclusions are exclusions from the *feature* set; they are listed in
`DATA_DICTIONARY.md`.

## Download this version

Release assets are **flat** (GitHub does not allow `/` in asset names). `get_dataset.py` restores
the runner's layout:

| asset | bytes | sha256 (first 16) | becomes |
|---|---|---|---|
| `train.csv` | 71,546,966 | `6fc37e034447b2e9` | `public/train.csv` |
| `eval.csv` | 35,801,537 | `241dee5eb84cfdd5` | `public/eval.csv` |
| `holdout.csv` | 24,075,321 | `738ff7ec245302ff` | `private/holdout.csv` |
| `meta.json` | 2,121 | `5dc8aed06c157a35` | `meta.json` |
| `quality.json` | 3,434 | `a7f9c99c5d0c9465` | `quality.json` |

`MANIFEST.json` records each file's full SHA-256, the artifact version, the source, and the
baseline. `SHA256SUMS` carries the same hashes in `sha256sum` format against the **laid-out**
paths.

By hand:

```bash
gh release download v2026.09 --repo earino/austin-911-response --dir ./flat
mkdir -p task/public task/private
cp flat/train.csv task/public/train.csv
cp flat/eval.csv task/public/eval.csv
cp flat/holdout.csv task/private/holdout.csv
cp flat/meta.json flat/quality.json task/
sha256sum -c SHA256SUMS      # run from ./task, with SHA256SUMS copied there
```

**Row counts and positive rates, measured:**

| split | period | rows | positives | positive rate |
|---|---|---|---|---|
| `public/train.csv` | before 2025-01-01 | 572,180 | 231,025 | 0.403763 |
| `public/eval.csv` | 2025 | 285,665 | 109,860 | 0.384576 |
| `private/holdout.csv` | 2026-01-01 onward | 191,791 | 72,450 | 0.377755 |
| **total** | | **1,049,636** | | |

The split is **temporal and never random**: train on the past, select on 2025, score on 2026
onward. Row counts equal the source's per-year counts exactly, so extraction lost and duplicated
nothing.

`meta.json` carries the machine-readable task description (`target`, `positive_label`,
`id_columns`, `columns`, `rows`, `positive_rate`, `split`, `description`) plus prediction time and
threshold. `quality.json` is the descriptor the qualification gate validated the rows against,
including the excluded post-hoc columns and the measured source properties.

**The holdout is included here and is intended to be public when this repository is.** It must
still be kept out of an evaluated agent's workspace during a benchmark run: it is labelled, so
exposing it to an agent being scored would defeat the evaluation. Its presence is for
reproducibility and independent scoring.

Categorical treatment: object-dtype columns are categorical. `train.py` treats string columns
with more than 1000 levels as too high-cardinality for its baseline and drops them, so `geoid`
and `blkgpnm` are dropped by that baseline even though they ship in the data. That is the
runner's documented behaviour, not a property of the dataset.

## Reproduce and evaluate

The dataset is reproducible **from this repository alone**. `code/build.py` is stdlib-only Python
3.13 and fetches the public API anonymously.

```bash
python3 code/build.py --out /tmp/extract \
    --built-at 2026-09-18T19:36:55.770697+00:00

cd /tmp/extract && sha256sum -c /path/to/repo/SHA256SUMS
```

**Pass `--built-at`.** `meta.json` embeds the build timestamp, so without it a rebuild differs in
that one field and its `artifact version` will not match. The pin is this release's recorded
`built_at_utc`. That is not a technicality: the first attempt at reproducing this version
rebuilt all three split files byte-for-byte and still failed verification for exactly this
reason.

**Measured cost of extraction.** **69 HTTP requests** and 353.7 s wall clock on a 2-vCPU / 2 GB
machine, producing ~136 MB. The 69 break down as 15 aggregate queries (1 row count, 10 threshold
probes, 1 re-measure, 3 per-split counts) plus 54 pages of rows at 20,000 per page (29 train,
15 eval, 10 holdout). No credential is needed.

**Qualification.** `code/qualify_dataset.py` is the gate that gated this version:

```bash
python3 code/qualify_dataset.py ./task          # all checks, exit non-zero on any failure
python3 code/qualify_dataset.py --selftest      # proves the gate still rejects its broken fixtures
```

The released version passed **33 checks, 0 failures**, gate version 1.3.0, over the full artifact.
Coverage:

- *Leakage* — every shipped column declared; no answer source or post-hoc column shipped; no
  single shipped column separates the classes on its own; high-cardinality columns declared.
- *Prediction timing* — the prediction instant declared; no feature documented as post-hoc; the
  label source is not a feature; every feature documented as available at prediction time.
- *Splits* — files present and non-empty; both classes in eval and holdout; declared positive
  counts recomputed from the rows; clustered event counts recomputed; **no identifier spans two
  splits**; repeated identifiers measured against the declared count; rates not uniform; actual
  row ranges disjoint and inside the declared windows; enough independent positive events.
- *Runner compatibility* — holdout private, train/eval public; `meta.json` carries every key the
  runner reads and agrees with the files; identifiers are not also features.

### The response-time clock, measured

The label comes from `response_time`, which the portal documents as beginning when the call was
**answered** — earlier than `response_datetime`. `code/measure_clock_offset.py` measures the gap
rather than assuming it:

```
delta_seconds = (first_unit_arrived_datetime - response_datetime) - response_time
```

Over the first **2,000 rows in `:id` order** (deterministic; re-run the script to reproduce):

| | |
|---|---|
| median | **−57 s** |
| mean | −53.5 s |
| p05 / p95 | −206 s / 0 s |
| range | −468 s … +6,041 s |
| negative (label clock starts earlier) | 1,890 of 2,000 |
| exactly zero agreement | 55 of 2,000 |
| positive (label clock starts later) | 55 of 2,000 |

So for the large majority of rows the label's clock starts about a minute **before** the
prediction instant, and it never starts earlier than ~8 minutes. This is a real, bounded
measurement limitation of the dataset: the window between the prediction instant and the start of
the measured clock is small but not zero.

### Measured baselines

Floors, not results:

| baseline | eval AUC | what it is |
|---|---|---|
| single feature (`initial_problem_category`, 40 levels) | **0.627031** | shipped in the extract's `manifest.json`; majority-class accuracy 0.615424 |
| the benchmark's own `train.py`, unmodified | **0.7691** | one run through the runner's training/validation contract |
| same, scored via `validate.py`'s `predict_proba` path | **0.7691** | the contract's own independent re-score; agrees |

The runner's baseline is XGBoost (30 trees, depth 6, `hist`, categorical support) with the
benchmark's own feature handling — string columns over 1000 levels dropped, unseen levels mapped
to NaN — trained on `train` and scored on `eval`. It took **2.6 s to train and 0.3 s to score**.
Reproduce it with `sh baseline/reproduce_baseline.sh ./task`; the runner files and their hashes
are in `baseline/`.

**No agent or harness comparison has been run.** 0.7691 is a floor for what an agent might do,
not a finding about any agent.

## Findings and limitations

**What the task measures.** How much information about a long wait is available at dispatch time,
and how much of the apparent difficulty is structural (call type, geography, hour).

**Known weaknesses, stated plainly.**

- The label's clock starts ~57 s before the prediction instant, on average (measured above).
- The source is a live catalogue the City updates, so a rebuild after 2026-09-18 will not
  reproduce these bytes. The hashes, not the source URL, define this version.
- `incident_number` is **not unique**: 24 of 1,049,636 rows share a number with another row
  (11 train, 7 eval, 6 holdout — all inside one split). **4 of those 24 pairs carry different
  labels**, because the two rows are different events that share a number — for example
  `230990471` is an "Alarms"/Baker call at 07:33 with a 618-second response *and* an
  "Other"/Frank call at 16:38 with a 6,164-second response. The dataset therefore does not claim
  `incident_number` identifies a unique entity; `quality.json` declares the count and states that
  no such claim is made.
- Class balance (~38–40% positive) follows from the physical threshold. It was deliberately not
  tuned to balance classes.
- `priority_level` and `mental_health_flag` are excluded as post-hoc even though they look
  useful: both are determined after the prediction instant, and a model allowed to see them would
  report performance it could not achieve in deployment.

**Attribution and citation.** Data: City of Austin, *APD 911 Calls for Service 2023-2026*, Austin
Open Data, Public Domain, accessed 2026-09-18.

> City of Austin. *APD 911 Calls for Service 2023-2026*. Austin Open Data. Public Domain.
> Accessed 2026-09-18. Derived dataset: Austin 911 response time prediction dataset, version
> 2026.09, artifact `e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328`.

**Versioning and corrections.** Releases are versioned `YYYY.MM`. A corrected rebuild gets a new
version and a changelog entry; previous versions and their hashes are kept rather than
overwritten, so a published result always names the artifact version it used.
