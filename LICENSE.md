# Licence and attribution

## The data

**Public Domain.** The source catalogue entry for `e687-fx2y` reports the licence as
`Public Domain`:

- Socrata catalogue metadata for `e687-fx2y`, queried 2026-09-18.
- Re-confirmed 2026-09-18 from `GET https://datahub.austintexas.gov/api/views/e687-fx2y.json`,
  which returns `"license": {"name": "Public Domain"}` for the view *APD 911 Calls for Service
  2023-2026*.

Redistribution of the source data is permitted on that basis. This dataset is a derived work: row
selection, a derived binary label, and a temporal partition. No row is edited, imputed,
reweighted or synthesised.

**Attribution.** City of Austin, *APD 911 Calls for Service 2023-2026*, Austin Open Data,
https://datahub.austintexas.gov/d/e687-fx2y, accessed 2026-09-18. Public Domain.

**Suggested citation text.**

> City of Austin. *APD 911 Calls for Service 2023-2026*. Austin Open Data. Public Domain.
> Accessed 2026-09-18. Derived dataset: Austin 911 response time prediction dataset, version
> 2026.09, artifact `e4598317e406984fa590aacc5e7aff675867578c51ae1a84ebf6279bc42c3328`.

## The holdout

The labelled holdout (`holdout.csv`) is **included in this repository's release assets and is
intended to become publicly downloadable** when this repository is made public. That decision is
made. It must still be kept out of an evaluated agent's workspace during a benchmark run: it is
labelled, so exposing it to an agent being scored would defeat the evaluation. See
`DATA_DICTIONARY.md`.

## The construction code in this repository

`code/build.py`, `code/qualify_dataset.py`, `code/materialize.py` and `code/measure_clock_offset.py`
are published here so the dataset is reproducible without the private factory repository.

**Their licence has not been chosen yet.** The data's Public Domain status says nothing about the
code that derives it, so this is left as an explicit decision rather than assumed:

- [ ] MIT
- [ ] Apache-2.0
- [ ] CC0
- [ ] No licence published (reproduction instructions only, all rights reserved)

Until one is chosen, treat these files as **all rights reserved**: you may read and run them to
verify this dataset, and no broader grant is implied.

## The baseline runner files

`baseline/train.py`, `baseline/validate.py` and `baseline/validate.sh` are copied **verbatim**
from `earino/harness_benchmark`, a private repository that carries **no licence file**. They are
included so the recorded baseline is reproducible from this repository alone.

Because that project has no licence, including these three files here is the maintainer's
decision to make and is recorded as such rather than presented as an established right. If this
repository is made public, that decision should be confirmed — either by choosing a licence for
the benchmark project or by removing the files and documenting the baseline as reproducible only
with access. `baseline/README.md` records their provenance and hashes.

Nothing in this repository is relicensed by the others' terms.
