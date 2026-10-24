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
