# The baseline runner, and why it is shipped here

`train.py`, `validate.py` and `validate.sh` are **copied verbatim** from `earino/harness_benchmark`
(file set `task_template/`). They are included so the baseline in `MANIFEST.json` is reproducible
from this repository alone, without access to that project.

| file | sha256 (must match `MANIFEST.json`) |
|---|---|
| `train.py` | `a3c6bcf13735bc85c52129ded68f839090dffdc266ebc3810dc61b2e6ea5e7e8` |
| `validate.py` | `b597e7f84fed614e64b4a86fbecbd6ec0145916a24d0d221a796586976418e7b` |
| `validate.sh` | `3f06ca48f11c2e05d331b4d8394284925de660c1d4b086d2f8243959e83b7e6d` |

**Provenance and permission.** Source: `earino/harness_benchmark`, file set `task_template/`,
retrieved 2026-09-18. That project is the copyright holder's own work, developed with Claude and
Szilard; the holder has confirmed permission to release these copies here **under MIT** (see
`../LICENSE.md` and `../LICENSE-MIT.txt`). Contributor credits are preserved: Copyright (c) 2026
E. Arino de la Rubia (earino), with contributors Claude and Szilard.

Credits recorded upstream are preserved too: the benchmark's autoresearch loop follows
[szilard/xgboost-autoresearch](https://github.com/szilard/xgboost-autoresearch), itself in the
tradition of [karpathy/autoresearch](https://github.com/karpathy/autoresearch). Those projects are
referenced, not distributed here, and their own terms apply to them.

The hashes above are unchanged from the recorded run, so the licence grant does not alter the
artifact: the worker job that produced the baseline number in `REPRODUCE.md` verified these hashes
on the machine before running them, and reported `unmodified: true`.

`train.py` is "the only file the agent edits" in the benchmark's own terminology. Nothing here
edits it: the point of shipping it is that the baseline is the *unmodified* baseline.
