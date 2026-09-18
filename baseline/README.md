# The baseline runner, and why it is shipped here

`train.py`, `validate.py` and `validate.sh` are **copied verbatim** from the harness benchmark
project, which is private. They are included so the baseline in `MANIFEST.json` is reproducible
from this repository alone, without access to that project.

| file | sha256 (must match `MANIFEST.json`) |
|---|---|
| `train.py` | `a3c6bcf13735bc85c52129ded68f839090dffdc266ebc3810dc61b2e6ea5e7e8` |
| `validate.py` | `b597e7f84fed614e64b4a86fbecbd6ec0145916a24d0d221a796586976418e7b` |
| `validate.sh` | `3f06ca48f11c2e05d331b4d8394284925de660c1d4b086d2f8243959e83b7e6d` |

**Provenance.** Source: `earino/harness_benchmark`, file set `task_template/`, retrieved
2026-09-18. The repository is private and carries **no licence file**, so these three files are
included here by the maintainer's decision for reproducibility and are **not** relicensed by
this dataset. If you redistribute this repository, treat that as the maintainer's call to make —
it is listed as an open item in `LICENSE.md`.

The recorded baseline run used these exact bytes: the worker job that produced the number in
`REPRODUCE.md` verified the hashes on the machine before running them, and reported
`unmodified: true`.

`train.py` is "the only file the agent edits" in the benchmark's own terminology. Nothing here
edits it: the point of shipping it is that the baseline is the *unmodified* baseline.
