# Verification record

This package was tested end-to-end from a **fresh consumer environment** before being handed over:
a container with no access to the factory pipeline, no GitHub credential, and nothing but the
published repository and the release assets as a consumer receives them.

Run: `austin-consumer-002`, 2026-09-18, elapsed **56.9 s**, exit **0**.

| step | result |
|---|---|
| the cloned package matches `MANIFEST.json` | 17 files checked, every hash matched |
| release assets downloaded (host-side, credential never in the container) | 5 files, **131,429,379 bytes**, every SHA-256 verified on arrival |
| `sha256sum -c SHA256SUMS` | `meta.json`, `private/holdout.csv`, `public/eval.csv`, `public/train.csv`, `quality.json` — all **OK** |
| `python3 code/qualify_dataset.py ./task` | **QUALIFICATION PASSED**, artifact version `e4598317e406984f` |
| `sh baseline/reproduce_baseline.sh ./task` | **`Eval AUC: 0.7691`**, `[validate] CONTRACT OK`, training 2.1 s |

The reproduced baseline matches the recorded value exactly, on the published bytes rather than on
a rebuild of them.

## What this run does and does not cover

- **Covered:** the documented verification command, the published gate over the published data,
  the published baseline, the package-hash check, and the download layout the assets arrive in.
- **Not covered in the container:** the *network* half of `get_dataset.py`. The container has no
  GitHub credential by design, so the download is performed by the worker host, which does hold
  one, and the container is given the result read-only. That download path is the same API call
  with the same SHA-256 verification, and it is what proved the 5 files above.
- **Not covered anywhere:** a rebuild from the source API. That is step 5 of `REPRODUCE.md` and
  was verified separately during construction; it needs ~136 MB of scratch space and is not part
  of the consumer check.

## Provenance

The dataset was built and qualified on a worker as job `austin-003` and the release assets were
transferred from private staging by job `austin-publish-003`, which verified every asset on
arrival and again from the server's own digest after upload. Both workers were destroyed
afterwards with the provider confirming zero servers and zero IPs remaining.
