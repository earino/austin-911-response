# Licence and attribution

Two grants with two scopes. They are kept apart on purpose: the code here is ours to license, and
the city's data is not ours to license at all.

## 1. Our code and documentation - MIT

Covered by `LICENSE-MIT.txt`: the construction, qualification and measurement scripts
(`code/*.py`), the baseline runner files (`baseline/*`), `get_dataset.py`, the dataset card and
data dictionary, this notice, and the reproduction and verification documents.

Copyright (c) 2026 E. Arino de la Rubia (earino), with contributors Claude and Szilard.

**The three baseline runner files.** `baseline/train.py`, `baseline/validate.py` and
`baseline/validate.sh` are copied **verbatim** from `earino/harness_benchmark`, file set
`task_template/`. That project is the copyright holder's own work, developed with Claude and
Szilard, and the holder has confirmed permission to release these copies under MIT. Contributor
credits are preserved above and in `baseline/README.md`. Their bytes are unchanged by this
licence: their hashes in `MANIFEST.json` are the same hashes the recorded baseline run verified
before running them, so the licence grant does not disturb the reproducible artifact.

`harness_benchmark` itself remains a private, read-only checkout for this work; this permission
covers the distributed copies only, and needed no edit to that project.

## 2. Our rights in the derived dataset - CC0-1.0

Covered by `LICENSE-CC0-1.0.txt`: **our contribution to the compilation** - the row selection, the
derived binary label, the temporal partition, and the packaging of the result.

**Scope, stated plainly: we dedicate our contribution; we do not claim ownership of the City of
Austin's data, and we do not relicense it.** The source data stays under its own terms (below),
and this dedication cannot and does not alter them. A downstream user receives our contribution
under CC0-1.0 and the city's data under its Public Domain designation, unchanged.

## 3. The source data - Public Domain, preserved

The source catalogue entry for `e687-fx2y` reports the licence as `Public Domain`:

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

This dataset is derived from the City of Austin's open data and is labelled as derived. It is not
an official City of Austin product, and nothing here should be presented as one.

## 4. The holdout

The labelled holdout (`holdout.csv`) is **included in this repository's release assets and is
intended to become publicly downloadable** when this repository is made public. That decision is
made. It must still be kept out of an evaluated agent's workspace during a benchmark run: it is
labelled, so exposing it to an agent being scored would defeat the evaluation. See
`DATA_DICTIONARY.md`.

## 5. What this notice does not cover

- The city's data, which remains under its own Public Domain designation.
- Third-party projects referenced but not distributed here; their own terms apply to them.
- Any trademark, name or logo of the City of Austin, or any implication of endorsement.
- Files under other terms, if a future version of this dataset adds any; they will be listed here.

## 6. Policy for future datasets in this series

Terms are chosen to be **compatible with each source**, and the same split applies: our code under
a permissive software licence, our contribution to the compilation under terms the source permits.

**CC0 is not a blanket override of upstream terms.** A source that requires attribution, share-alike
or non-commercial use gets those terms, and a source whose licence cannot be read is not published
at all. Before any release, `dataset-discovery` must have closed the licence contract for every
source with the terms actually read, and the chosen terms are recorded in the release manifest.
