#!/usr/bin/env python3
"""Construction script for the `austin-911-response` candidate.

Builds the train / eval / holdout extracts for the task "will the first officer arrive
more than T minutes after the Austin police 911 call was answered?".

Where this runs
---------------
**On a temporary worker, not on the coordinator.** The full series is ~1,050,000 rows and
the coordinator has 1.9 GiB of RAM and ~6 GB of disk. Use `--limit` for a bounded local
exercise that proves the script works without pulling the whole series.

The script is stdlib-only, mirroring the rest of the factory code.

Output layout - the existing runner's contract
----------------------------------------------
The extracts are written in the layout `../harness_benchmark` consumes, so a constructed
dataset can be handed to the runner without a conversion step:

    <out>/public/train.csv      labeled training data   (copied into the agent's workdir)
    <out>/public/eval.csv       labeled evaluation data (the agent's keep/discard signal)
    <out>/private/holdout.csv   labeled holdout         (never copied into a workdir)
    <out>/meta.json             target, positive label, id columns, rows, positive rates

`manifest.json` and `summary.json` are also written for the worker's report contract.

**Why the raw response time is NOT in any CSV.** The runner treats every column other
than the target as model input: `train.py` excludes only `id_columns` and the target when
choosing features, and `validate.py` hands `predict_proba` the full frame with only the
target dropped. So a declared feature list does not protect anything - a column that ships
is a column a solver can use. `response_time` determines the label directly, so it is
fetched to derive `late` and then excluded from every file. The manifest records it as
`label_source_column` for provenance.

Leakage discipline, from the candidate notes
--------------------------------------------
Features are dispatch-time only. `priority_level` (assigned at the officer's arrival) and
`mental_health_flag` (settable from the final problem description and the call disposition)
are post-hoc and are excluded, together with every arrival, closing, disposition, unit,
injury and final-classification field. The target uses the portal's own `response_time`
column, which begins when the call was *answered* - earlier than `response_datetime` - so it
can never be recomputed from the timestamps in the row.

The output directory is also checked by `skills/dataset-qualification/`, which is the
project's gate before a candidate goes to the benchmark.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATASET = "e687-fx2y"
BASE = "https://datahub.austintexas.gov"
USER_AGENT = {"User-Agent": "scout-dataset-factory/0.1 (construction)"}

# Dispatch-time features. `response_day_of_week` and `response_hour` are the portal's own
# derivations of `response_datetime`; nothing here is known only after the response.
FEATURES = [
    "incident_type",
    "sector",
    "council_district",
    "geoid",
    "blkgpnm",
    "response_day_of_week",
    "response_hour",
    "initial_problem_description",
    "initial_problem_category",
]

# Carried alongside the features: an identifier for reconciliation, and the timestamp the
# prediction is made at. Neither determines the label.
CARRY_COLUMNS = ["incident_number", "response_datetime"]

# Fetched only to derive `late`. Never written to a CSV.
LABEL_SOURCE = "response_time"

LABEL_COLUMN = "late"

# Columns deliberately excluded, recorded so the exclusion is auditable rather than implied.
EXCLUDED_POST_HOC = [
    "priority_level",
    "mental_health_flag",
    "first_unit_arrived_datetime",
    "call_closed_datetime",
    "final_problem_description",
    "final_problem_category",
    "call_disposition_description",
    "number_of_units_arrived",
    "unit_time_on_scene",
    "report_written_flag",
    "officer_injured_killed_count",
    "subject_injured_killed_count",
    "other_injured_killed_count",
    LABEL_SOURCE,
]

SPLIT_WINDOWS = {
    "train": {"start": None, "end": "2025-01-01T00:00:00.000"},
    "eval": {"start": "2025-01-01T00:00:00.000", "end": "2026-01-01T00:00:00.000"},
    "holdout": {"start": "2026-01-01T00:00:00.000", "end": None},
}


def _window_predicate(column: str, window: dict) -> str:
    clauses = []
    if window["start"]:
        clauses.append(f"{column} >= '{window['start']}'")
    if window["end"]:
        clauses.append(f"{column} < '{window['end']}'")
    return " AND ".join(clauses)


# The query predicates and the windows published to the qualification gate are derived from
# one declaration, so the rows cannot end up outside the window the gate checks them against.
SPLITS = [(name, _window_predicate("response_datetime", SPLIT_WINDOWS[name]))
          for name in ("train", "eval", "holdout")]

# Runner layout: holdout is private, the other two are copied into the agent's workdir.
LAYOUT = {"train": Path("public") / "train.csv",
          "eval": Path("public") / "eval.csv",
          "holdout": Path("private") / "holdout.csv"}

TRAIN_WHERE = SPLITS[0][1]
ELIGIBLE = f"{LABEL_SOURCE} IS NOT NULL"

POSITIVE_LABEL = 1

# Rebuilds must clear only what this script owns. An arbitrary `--out` path must never be
# recursively deleted: the directory is cleared only when it carries the marker this script
# writes at creation, and then only the generated entries are removed.
OWNED_MARKER = ".dataset-factory-extract"
GENERATED_PATHS = ["public", "private", "meta.json", "manifest.json", "summary.json",
                   "quality.json"]
FORBIDDEN_OUT = ("/", "/etc", "/usr", "/var", "/opt/data", "/root", "/home")


def prepare_output(out: Path) -> None:
    """Clear a previously generated extract, or refuse.

    Refuses a protected path, a directory containing a `.git`, anything that is not a
    directory, and a non-empty directory this script did not create. A destructive default is
    how uncommitted work gets lost.

    The protected-path check runs *before* the existence check on purpose: a protected path
    must be refused whether or not it happens to exist on this machine, so the behaviour does
    not depend on which host is running.
    """
    resolved = out.expanduser()
    if resolved.resolve() in {Path(p).resolve() for p in FORBIDDEN_OUT}:
        raise SystemExit(f"refusing --out {resolved}: that is a protected path")
    if resolved.exists():
        if (resolved / ".git").exists():
            raise SystemExit(f"refusing --out {resolved}: it contains a .git directory")
        if not resolved.is_dir():
            raise SystemExit(f"refusing --out {resolved}: it exists and is not a directory")
        if not (resolved / OWNED_MARKER).is_file():
            entries = sorted(entry.name for entry in resolved.iterdir())
            if entries:
                raise SystemExit(
                    f"refusing to clear {resolved}: it was not created by this script "
                    f"(no {OWNED_MARKER}) and holds {len(entries)} entr"
                    f"{'y' if len(entries) == 1 else 'ies'}: {entries[:8]}. "
                    "Point --out at an empty directory or a previously generated extract."
                )
        else:
            for relative in GENERATED_PATHS:
                target = resolved / relative
                if target.is_dir():
                    shutil.rmtree(target)
                elif target.exists():
                    target.unlink()
    resolved.mkdir(parents=True, exist_ok=True)
    (resolved / OWNED_MARKER).write_text(
        "Generated by candidates/austin-911-response/source/build.py. Safe to clear.\n")


def get_json(url: str, attempts: int = 4, timeout: int = 180):
    last = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=USER_AGENT)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:160]}"
        except Exception as exc:  # noqa: BLE001
            last = repr(exc)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"request failed after {attempts} attempts: {last}")


def resource_url(params: dict) -> str:
    return f"{BASE}/resource/{DATASET}.json?" + urllib.parse.urlencode(params)


def count(where: str) -> int:
    rows = get_json(resource_url({"$select": "count(*) AS n", "$where": where}))
    return int(rows[0]["n"]) if rows else 0


def freeze_threshold(target_rate: float, lo: int = 0, hi: int = 21600) -> dict:
    """Binary-search T so P(response_time > T) in the TRAINING WINDOW is near target_rate.

    Aggregate COUNT queries only, so this costs no row downloads. The returned T is the
    largest tested value whose training rate is still at or above the target, which keeps
    the choice monotone and reproducible.
    """
    base = count(f"{ELIGIBLE} AND {TRAIN_WHERE}")
    if not base:
        raise RuntimeError("training window is empty; check the split boundaries")

    probes = []

    def rate_at(threshold: int) -> float:
        n = count(f"{ELIGIBLE} AND {TRAIN_WHERE} AND {LABEL_SOURCE} > {threshold}")
        probes.append({"threshold_seconds": threshold, "n_above": n, "rate": n / base})
        return n / base

    low, high = lo, hi
    while high - low > 60:
        mid = ((low + high) // 2 // 60) * 60
        if mid <= low:
            break
        if rate_at(mid) >= target_rate:
            low = mid
        else:
            high = mid

    chosen = low
    # Snap to the nearest whole minute and re-measure for the record.
    chosen = int(round(chosen / 60.0)) * 60
    chosen_rate = rate_at(chosen)
    return {
        "threshold_seconds": chosen,
        "threshold_minutes": chosen // 60,
        "training_rows": base,
        "training_rate_at_threshold": round(chosen_rate, 6),
        "target_rate": target_rate,
        "probes": probes,
        "rule": "binary search on the training-window aggregate so P(response_time > T) "
                "is just at or above the target rate; frozen before any row is scored",
    }


def stream_rows(where: str, select: str, page_size: int, limit: int | None = None,
                order: str = "incident_number,:id"):
    """Yield rows in a total order. The order key must be unique per row, or offset paging
    can repeat or skip rows whose sort keys tie.

    `incident_number` is NOT unique in this dataset - 24 incident numbers carry two rows - so
    ordering by it alone leaves ties whose order the backend may resolve differently between
    requests. Socrata's `:id` is unique per row (verified: 1,049,636 rows, 1,049,636 distinct),
    so `incident_number,:id` is total and the paging is deterministic.
    """
    offset = 0
    seen = 0
    while True:
        want = page_size if limit is None else min(page_size, limit - seen)
        if want <= 0:
            return
        params = {"$select": select, "$where": where, "$order": order,
                  "$limit": str(want), "$offset": str(offset)}
        rows = get_json(resource_url(params))
        if not rows:
            return
        for row in rows:
            yield row
        seen += len(rows)
        offset += len(rows)
        if len(rows) < want:
            return


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def label_for(response_time, threshold_seconds: int) -> int:
    """Strict comparison, matching the aggregate used to freeze the threshold."""
    return int(float(response_time) > threshold_seconds)


def auc_from_scores(labels: list[int], scores: list[float]) -> float | None:
    """Rank-based ROC AUC, ties averaged. Pure stdlib so the worker needs no ML stack."""
    if len(labels) != len(scores):
        raise ValueError("labels and scores must align")
    pairs = sorted(zip(scores, labels), key=lambda pair: pair[0])
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    rank_sum = 0.0
    index = 0
    while index < len(pairs):
        end = index
        while end + 1 < len(pairs) and pairs[end + 1][0] == pairs[index][0]:
            end += 1
        average_rank = (index + end) / 2.0 + 1.0
        for position in range(index, end + 1):
            if pairs[position][1] == 1:
                rank_sum += average_rank
        index = end + 1
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def category_rate_baseline(train_rows: list[dict], scored_rows: list[dict],
                           column: str = "initial_problem_category") -> dict:
    """A one-rule baseline: score a row by its category's training-window positive rate."""
    positives: dict[str, int] = {}
    totals: dict[str, int] = {}
    for row in train_rows:
        key = row.get(column) or "(missing)"
        totals[key] = totals.get(key, 0) + 1
        positives[key] = positives.get(key, 0) + int(row[LABEL_COLUMN])
    base_rate = (sum(positives.values()) / len(train_rows)) if train_rows else 0.0
    rates = {key: positives.get(key, 0) / totals[key] for key in totals}

    labels = [int(row[LABEL_COLUMN]) for row in scored_rows]
    scores = [rates.get(row.get(column) or "(missing)", base_rate) for row in scored_rows]
    auc = auc_from_scores(labels, scores)
    positive = sum(labels)
    majority_accuracy = (max(positive, len(labels) - positive) / len(labels)) if labels else None
    return {
        "column": column,
        "categories_in_train": len(rates),
        "training_base_rate": round(base_rate, 6),
        "rows_scored": len(scored_rows),
        "positives": positive,
        "auc": round(auc, 6) if auc is not None else None,
        "majority_class_accuracy": round(majority_accuracy, 6) if majority_accuracy else None,
        "note": "single-feature baseline; a competent model must beat this AUC",
    }


def write_quality(out: Path, manifest: dict, fieldnames: list[str],
                  positive_days: dict[str, int]) -> None:
    """The qualification gate's descriptor, written beside the extract.

    Everything here is measured from the rows that were just written, so the gate can compare
    the declaration against the files rather than trusting either alone.
    """
    splits = {entry["name"]: entry for entry in manifest["splits"]}
    quality = {
        "name": "austin-911-response",
        "task": {
            "question": manifest["prediction_question"],
            "prediction_time": manifest["prediction_time"],
        },
        "target": LABEL_COLUMN,
        "positive_label": POSITIVE_LABEL,
        "threshold_seconds": manifest["threshold"]["threshold_seconds"],
        "time_column": "response_datetime",
        "event_key_column": "response_datetime",
        "features": FEATURES,
        "features_documented_at": "prediction_time",
        "carry_columns": CARRY_COLUMNS,
        "id_columns": ["incident_number"],
        # incident_number is not unique in the source: 24 of its 1,049,636 rows repeat an
        # incident number, so a handful of rows share an identifier with a row in the same
        # split. That is the source's grain, not split leakage, and the count is measured from
        # the rows just written. Declaring it pins the known-good value: if paging ever starts
        # repeating rows, the gate sees a count above this and fails.
        "expected_duplicate_ids": sum(entry["duplicate_incident_numbers"]
                                      for entry in manifest["splits"]),
        "expected_duplicate_ids_by_split": {entry["name"]: entry["duplicate_incident_numbers"]
                                            for entry in manifest["splits"]},
        # Deliberately NOT claiming `id_columns_are_entity_keys`. The repeated incident numbers
        # are two different events that happen to share a number - hours apart, different
        # categories, different sectors - so one label per incident number is not a property
        # this source has. The gate records the measured disagreement instead of refusing the
        # dataset for a claim the source does not make.
        "id_columns_note": "incident_number identifies a call, not a row, and is not unique: "
                           "24 of 1,049,636 source rows share a number with another row, and 4 "
                           "of those pairs carry different labels because they are separate "
                           "events. The unique per-row key is the catalogue's :id, used only "
                           "for deterministic paging.",
        "repeated_identifier_labels_measured": {
            "repeated_identifiers": sum(entry["duplicate_incident_numbers"]
                                        for entry in manifest["splits"]),
            "differing_labels": sum(entry["duplicate_incident_numbers_differing_labels"]
                                    for entry in manifest["splits"]),
        },
        "high_cardinality_columns": ["response_datetime", "initial_problem_description"],
        "label_source_columns": [LABEL_SOURCE],
        "post_hoc_columns": EXCLUDED_POST_HOC,
        "measurements": [
            {"column": LABEL_SOURCE, "unit": "seconds",
             "frame": "portal column; begins when the 911 call was answered, which is "
                      "earlier than response_datetime"},
        ],
        "splits": {name: entry["file"] for name, entry in splits.items()},
        "split_boundaries": {name: where for name, where in SPLITS},
        "split_windows": SPLIT_WINDOWS,
        "positive_events": {
            name: {"positives": splits[name]["positives"],
                   "distinct_events": positive_days[name]}
            for name in ("eval", "holdout")
        },
        "positive_events_note": "distinct_events counts calendar days carrying at least one "
                                "positive, which is the conservative reading of clustering "
                                "for this source; calls on a busy day are not independent "
                                "in the sense the gate is checking.",
        "built_at_utc": manifest["built_at_utc"],
        "shipped_columns": fieldnames,
    }
    (out / "quality.json").write_text(json.dumps(quality, indent=1) + "\n")


def write_meta(out: Path, manifest: dict, fieldnames: list[str]) -> None:
    """meta.json in the runner's shape, plus the provenance the qualification gate reads."""
    splits = {entry["name"]: entry for entry in manifest["splits"]}
    meta = {
        "name": "austin-911-response",
        "description": manifest["prediction_question"],
        "source": manifest["endpoint"],
        "license": "Public Domain (Socrata catalog metadata for e687-fx2y)",
        "target": LABEL_COLUMN,
        "positive_label": POSITIVE_LABEL,
        "id_columns": ["incident_number"],
        "columns": fieldnames,
        "rows": {name: splits[name]["rows"] for name in LAYOUT},
        "positive_rate": {name: splits[name]["positive_rate"] for name in LAYOUT},
        "split": {
            "strategy": "temporal by response_datetime",
            "boundaries": {name: where for name, where in SPLITS},
        },
        "threshold_seconds": manifest["threshold"]["threshold_seconds"],
        "label_rule": manifest["label_rule"],
        "label_source_column": LABEL_SOURCE,
        "prediction_time": manifest["prediction_time"],
        "features": manifest["features"],
        "excluded_post_hoc": manifest["excluded_post_hoc"],
        "carry_columns": manifest["carry_columns"],
        "built_at_utc": manifest["built_at_utc"],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the austin-911-response extracts")
    parser.add_argument("--out", default="/output",
                        help="output directory for the extracts (default: /output on a worker)")
    parser.add_argument("--target-rate", type=float, default=0.40,
                        help="training-window positive rate the threshold T is frozen at")
    parser.add_argument("--page-size", type=int, default=20000)
    parser.add_argument("--built-at", default=None,
                        help="pin built_at_utc (ISO 8601) so a rebuild of an existing artifact "
                             "is byte-identical; needed to reproduce a published version")
    parser.add_argument("--limit", type=int, default=None,
                        help="cap rows PER SPLIT; for a bounded coordinator exercise only")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--keep-flat", action="store_true",
                        help="also write flat <name>.csv copies beside the runner layout")
    args = parser.parse_args(argv)

    out = Path(args.out)
    prepare_output(out)

    print(f"dataset {DATASET}: total rows {count('1=1')}")
    print("freezing threshold T from the training window only")
    threshold = freeze_threshold(args.target_rate)
    print(f"  T = {threshold['threshold_seconds']}s "
          f"({threshold['threshold_minutes']} min), training rate "
          f"{threshold['training_rate_at_threshold']:.4f} "
          f"against a target of {threshold['target_rate']:.2f}")

    # The label source is fetched so `late` can be derived; it is never written out.
    select = ", ".join(CARRY_COLUMNS + FEATURES + [LABEL_SOURCE])
    fieldnames = CARRY_COLUMNS + FEATURES + [LABEL_COLUMN]
    prediction_question = ("Will the first officer arrive more than "
                           f"{threshold['threshold_minutes']} minutes after the Austin "
                           "police 911 call was answered?")

    manifest = {
        "candidate": "austin-911-response",
        "dataset": DATASET,
        "endpoint": f"{BASE}/resource/{DATASET}.json",
        "built_at_utc": args.built_at or datetime.now(timezone.utc).isoformat(),
        "prediction_question": prediction_question,
        "prediction_time": "At dispatch: the moment the 911 call-taker's ECT screen opens "
                           "(response_datetime). Only fields known then are shipped.",
        "threshold": threshold,
        "features": FEATURES,
        "carry_columns": CARRY_COLUMNS,
        "excluded_post_hoc": EXCLUDED_POST_HOC,
        "label_column": LABEL_COLUMN,
        "label_source_column": LABEL_SOURCE,
        "label_rule": f"late = 1 if {LABEL_SOURCE} > {threshold['threshold_seconds']} else 0",
        "shipped_columns": fieldnames,
        "layout": {name: str(path) for name, path in LAYOUT.items()},
        "splits": [],
        "limit_per_split": args.limit,
    }

    retained: list[dict] = []
    stats = {name: {"positive_days": set()} for name, _ in SPLITS}
    seen_ids: dict[str, set] = {name: set() for name, _ in SPLITS}
    duplicate_rows: dict[str, int] = {name: 0 for name, _ in SPLITS}
    first_labels: dict[str, dict[str, int]] = {name: {} for name, _ in SPLITS}
    contradictory_rows: dict[str, int] = {name: 0 for name, _ in SPLITS}

    for name, where in SPLITS:
        path = out / LAYOUT[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        rows_written = 0
        positives = 0
        nulls = 0
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames,
                                    extrasaction="ignore")
            writer.writeheader()
            for row in stream_rows(f"{ELIGIBLE} AND {where}", select,
                                   args.page_size, args.limit):
                response_time = row.get(LABEL_SOURCE)
                if response_time in (None, ""):
                    nulls += 1
                    continue
                record = {column: row.get(column, "") for column in CARRY_COLUMNS + FEATURES}
                record[LABEL_COLUMN] = label_for(response_time,
                                                 threshold["threshold_seconds"])
                incident = record["incident_number"]
                if incident in seen_ids[name]:
                    duplicate_rows[name] += 1
                    if first_labels[name].get(incident) != record[LABEL_COLUMN]:
                        contradictory_rows[name] += 1
                else:
                    seen_ids[name].add(incident)
                    first_labels[name][incident] = record[LABEL_COLUMN]
                writer.writerow(record)
                rows_written += 1
                positives += record[LABEL_COLUMN]
                if record[LABEL_COLUMN]:
                    stats[name]["positive_days"].add(str(record["response_datetime"])[:10])
                if name == "train" and not args.skip_baseline:
                    retained.append(dict(record))
        entry = {
            "name": name,
            "where": where,
            "file": str(LAYOUT[name]),
            "rows": rows_written,
            "positives": positives,
            "positive_rate": round(positives / rows_written, 6) if rows_written else None,
            "skipped_null_label_source": nulls,
            "positive_days": len(stats[name]["positive_days"]),
            "duplicate_incident_numbers": duplicate_rows[name],
            "duplicate_incident_numbers_differing_labels": contradictory_rows[name],
            "sha256": sha256_of(path),
            "bytes": path.stat().st_size,
            "columns": fieldnames,
        }
        manifest["splits"].append(entry)
        print(f"  {name:<8} rows={rows_written:>8} positives={positives:>7} "
              f"rate={entry['positive_rate']} sha256={entry['sha256'][:16]}...")

        if name == "eval" and not args.skip_baseline and retained:
            with (out / LAYOUT["eval"]).open(encoding="utf-8") as handle:
                eval_rows = list(csv.DictReader(handle))
            manifest["baseline"] = category_rate_baseline(retained, eval_rows)
            print(f"  baseline AUC on eval: {manifest['baseline']['auc']} "
                  f"(majority-class accuracy "
                  f"{manifest['baseline']['majority_class_accuracy']})")

        if args.keep_flat:
            shutil.copyfile(path, out / f"{name}.csv")

    positive_days = {name: len(stats[name]["positive_days"]) for name in stats}
    write_meta(out, manifest, fieldnames)
    write_quality(out, manifest, fieldnames, positive_days)

    summary = {
        "candidate": "austin-911-response",
        "status": "extract-built",
        "threshold_seconds": threshold["threshold_seconds"],
        "splits": {entry["name"]: {"rows": entry["rows"],
                                  "positives": entry["positives"],
                                  "positive_rate": entry["positive_rate"]}
                   for entry in manifest["splits"]},
        "baseline_auc_eval": (manifest.get("baseline") or {}).get("auc"),
        "features": FEATURES,
        "label_source_column_excluded_from_csv": LABEL_SOURCE,
        "note": "Measured extract with checksums, in the runner's public/private layout. "
                "Not a scored result; no model comparison yet.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(f"\nwrote {out}/public, {out}/private, {out}/meta.json, "
          f"{out}/manifest.json, {out}/summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
