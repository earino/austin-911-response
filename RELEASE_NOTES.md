<!-- dataset-factory:links -->
**Dataset Factory · v2026.09**

[Dataset website](https://earino.github.io/austin-911-response/versions/v2026.09/) · [GitHub release](https://github.com/earino/austin-911-response/releases/tag/v2026.09) · [Hugging Face](https://huggingface.co/datasets/earino/austin-911-response/tree/v2026.09) · [Catalogue](https://earino.github.io/dataset-factory-site/)

Artifact: e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328

### Suitability and evaluation requirements

Retained for retrospective model-development research with documented timing limitations. No answer recovery was found in the bounded audit; historical forecasting validity remains unverified.

**Supported uses:** Retrospective train/validation model-development experiments under the documented timing and selection limitations; Final evaluation only under a protocol that isolates holdout data from development and prevents later rows influencing earlier predictions

**Not supported:** Claims of verified real-time or operational forecasting validity; Treating development/validation scores as untouched final-test results

**Evaluation access:** chronological. The labeled eval split is development/validation data. Keep the final holdout outside agent development; prevent later rows from influencing earlier predictions.

**Historical availability:** assumed. **Training-label timing:** unverified. **Vintage:** current snapshot. **Selection:** unverified.

**Cross-row audit:** bounded no recovery. Bounded attack search, 15 active minutes per repository, frozen plan; not a security proof Holdout recovery was not tested by this audit.

Structural qualification and baseline scores do not certify operational forecasting validity.

- The bounded leakage audit's strongest lookup (identical full feature vector matched to unanimous train labels) covered 75,300/285,665 eval rows with 25,154 mismatches, AUC 0.6386: context memorization, not answer reconstruction - but a bounded search is not an absence proof.
- Historical feature/label availability at the declared prediction instant is assumed from current snapshots, not verified against release vintages.
- The current scorer passes the complete feature frame to predict_proba; prediction-time isolation is instructed but not mechanically enforced.
- The response-time outcome clock begins when the call was answered, before the dispatch prediction instant; this is not a forecast of a fresh full 20-minute interval.

Review: 2026-10-24; applies to v2026.09 / `e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328`. Frozen data and tags are unchanged.
<!-- /dataset-factory:links -->

# Austin 911 response time — `v2026.09`

First release. A leakage-checked, time-split prediction dataset built from the City of Austin's
public `APD 911 Calls for Service 2023-2026` records: predict, **at the moment a call is
dispatched**, whether the first unit will reach the caller more than 20 minutes later.

**1,049,636 rows**, three time-separated splits, Public Domain source data. **Public since
2026-09-19**, released after explicit operator authorisation. Publication changed no data file,
tag or checksum.

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

## Licensing, and the one decision still open

**Resolved 2026-09-19.** The code and documentation in this repository — including the three
baseline runner files copied verbatim from `earino/harness_benchmark` — are released under **MIT**
(`LICENSE-MIT.txt`). The copyright holder of that project confirmed permission for the copies,
with contributor credits preserved: Copyright (c) 2026 E. Arino de la Rubia (earino), with
contributors Claude and Szilard.

**Our rights in the derived compilation** are dedicated under **CC0-1.0**
(`LICENSE-CC0-1.0.txt`). The dedication covers our contribution — row selection, the derived
label, the temporal partition and the packaging — and does **not** cover or relicense the City of
Austin's data, which keeps its own **Public Domain** designation, attribution and suggested
citation unchanged.

**Still open: public visibility.** Nothing is public yet, on either platform, by instruction.

## Citation

> City of Austin. *APD 911 Calls for Service 2023-2026*. Austin Open Data. Public Domain.
> Accessed 2026-09-18. Derived dataset: Austin 911 response time prediction dataset, version
> 2026.09, artifact `e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328`.
