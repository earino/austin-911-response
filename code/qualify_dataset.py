#!/usr/bin/env python3
"""Dataset qualification gate.

Runs the five checks that stand between a constructed dataset and a scored claim:

  1. leakage        - no shipped column may determine the target
  2. prediction time- every shipped feature must be knowable when the prediction is made
  3. units / frames - values compared to an external threshold must declare unit and frame
  4. splits         - disjoint, correctly ordered, and carrying enough positives AND enough
                      negatives, judged from the actual rows rather than the declarations
  5. runner         - the extract must match the existing runner's input contract

Usage:

    python3 qualify_dataset.py <dataset-dir> [--json]
    python3 qualify_dataset.py --accept <report.json> <dataset-dir>
    python3 qualify_dataset.py --selftest

`<dataset-dir>` holds the runner layout (`public/train.csv`, `public/eval.csv`,
`private/holdout.csv`, `meta.json`) plus a `quality.json` descriptor. Exit status is 0 only
when every check passes.

`--accept` is the downstream gate: it re-verifies that a previously written report passed
**and** that its recorded artifact hashes still match the files on disk. Nothing may be
scored or accepted without one.

Design notes worth keeping:

* **A declared feature list proves nothing.** The runner hands every non-target column to
  prediction code, so the only reliable leak test is to look for a shipped column that
  separates the classes on its own.
* **Declarations are not evidence.** Split boundaries, positive counts and event counts are
  recorded in `quality.json` *and* recomputed from the rows. A dataset whose declarations are
  internally consistent but whose rows disagree must fail - that is exactly how an evaluation
  split ends up inside the training period, or with no negatives at all.
* **Unique-valued columns are not leaks by themselves.** An identifier or a free timestamp
  reaches a perfect AUC by memorising one row per level, which says nothing. Such columns are
  reported as high-cardinality and must be declared, not treated as leaks.
* **Uniform results are a red flag, not a finding.** Splits that are all-positive or
  all-negative are refused, because that is what a unit or reference-frame error looks like.
* **Full-dataset shape.** Splits are read column-wise, and the categorical scan builds its
  per-level statistics once instead of once per row, so a million-row extract costs linear
  memory and roughly linear time.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

GATE_VERSION = "1.3.0"

MIN_GROUP_FOR_CATEGORICAL = 5
MIN_EVAL_POSITIVES = 30
MIN_DISTINCT_EVENTS = 20


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def auc_from_scores(labels: list[int], scores: list[float]) -> float | None:
    """Rank-based ROC AUC with ties averaged. Stdlib only."""
    if len(labels) != len(scores) or not labels:
        raise ValueError("labels and scores must align and be non-empty")
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


def numeric_scores(values) -> list[float] | None:
    """Return the values as floats, or None when the column is not numeric."""
    try:
        return [float(value) for value in values]
    except (TypeError, ValueError):
        return None


def group_rates(values, labels) -> tuple[dict[str, float], int]:
    """Per-level positive rate, computed once for the whole column.

    Computing this inside the per-row loop is quadratic on a full dataset: each row would
    re-sum its entire level. One pass builds the level table, one pass scores the rows.
    """
    totals: dict[str, int] = {}
    positives: dict[str, int] = {}
    for value, label in zip(values, labels):
        totals[value] = totals.get(value, 0) + 1
        if label:
            positives[value] = positives.get(value, 0) + 1
    return ({value: positives.get(value, 0) / count for value, count in totals.items()},
            len(totals))


def column_leak_score(values, labels: list[int]) -> dict:
    """Score one column as a potential answer source.

    Numeric columns are used directly. Categorical columns are scored by their per-level
    positive rate, but only when every level carries at least MIN_GROUP_FOR_CATEGORICAL rows -
    otherwise the encoding memorises individual rows and a perfect score means nothing. Those
    columns are reported separately as high_cardinality.
    """
    scores = numeric_scores(values)
    if scores is not None:
        auc = auc_from_scores(labels, scores)
        return {"kind": "numeric", "auc": auc, "levels": None,
                "determines_label": auc in (0.0, 1.0)}

    rates, levels = group_rates(values, labels)
    if levels > max(1, len(labels) // MIN_GROUP_FOR_CATEGORICAL):
        return {"kind": "high_cardinality", "auc": None, "levels": levels,
                "determines_label": False}
    auc = auc_from_scores(labels, [rates[value] for value in values])
    return {"kind": "categorical", "auc": auc, "levels": levels,
            "determines_label": auc in (0.0, 1.0)}


def read_columns(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    """Read a CSV column-wise. A list-of-dicts costs about 1 KiB per row, which is hundreds
    of megabytes on a full extract; parallel column lists are a fraction of that."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            fieldnames = next(reader)
        except StopIteration:
            return [], {}
        columns: dict[str, list[str]] = {name: [] for name in fieldnames}
        for row in reader:
            for index, name in enumerate(fieldnames):
                columns[name].append(row[index] if index < len(row) else "")
    return fieldnames, columns


def header_of(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle), [])


class Report:
    def __init__(self, dataset: Path):
        self.dataset = str(dataset)
        self.gate_version = GATE_VERSION
        self.results: list[dict] = []
        self.artifact: dict[str, dict] = {}

    def add(self, check: str, ok: bool, detail: str, evidence=None):
        self.results.append({"check": check, "ok": bool(ok), "detail": detail,
                             "evidence": evidence or {}})

    @property
    def ok(self) -> bool:
        return all(result["ok"] for result in self.results)

    def render(self) -> str:
        return "\n".join(
            f"[{'PASS' if result['ok'] else 'FAIL'}] {result['check']}: {result['detail']}"
            for result in self.results)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "dataset": self.dataset,
            "gate_version": self.gate_version,
            "artifact": self.artifact,
            "results": self.results,
            "failed_checks": [r["check"] for r in self.results if not r["ok"]],
        }


def check_leakage(dataset: Path, quality: dict, report: Report,
                  columns_by_split: dict) -> None:
    target = quality["target"]
    shipped: set[str] = set()
    for fieldnames, _ in columns_by_split.values():
        shipped |= set(fieldnames)
    declared = set(quality.get("features", [])) | set(quality.get("carry_columns", [])) \
        | set(quality.get("id_columns", [])) | set(quality.get("high_cardinality_columns", [])) \
        | {target}
    undeclared = sorted(shipped - declared)
    report.add("leakage.declared_columns",
               not undeclared,
               "every shipped column is declared" if not undeclared
               else f"undeclared shipped columns: {undeclared}",
               {"undeclared": undeclared})

    forbidden = set(quality.get("label_source_columns", [])) | set(quality.get("post_hoc_columns", []))
    leaked_columns = sorted(shipped & forbidden)
    report.add("leakage.answer_source_absent",
               not leaked_columns,
               "no answer source or post-hoc column is shipped" if not leaked_columns
               else f"shipped columns that determine or postdate the label: {leaked_columns}",
               {"shipped_forbidden": leaked_columns})

    offenders, high_card, missing = [], [], []
    for name, (fieldnames, columns) in columns_by_split.items():
        if not columns or not columns.get(target):
            missing.append(name)
            continue
        labels = [int(value == str(quality["positive_label"])) for value in columns[target]]
        for column in fieldnames:
            if column == target:
                continue
            finding = column_leak_score(columns[column], labels)
            if finding["determines_label"]:
                offenders.append({**finding, "column": column, "split": name})
            elif finding["kind"] == "high_cardinality":
                high_card.append({"column": column, "split": name,
                                  "levels": finding["levels"]})
    report.add("leakage.no_single_column_determines_the_target",
               not offenders,
               "no shipped column separates the classes on its own" if not offenders
               else "columns reconstruct the label: "
                    + ", ".join(sorted({f"{o['column']}@{o['split']}" for o in offenders})),
               {"offenders": offenders,
                "high_cardinality": sorted({f"{h['column']}@{h['split']}" for h in high_card}),
                "missing_splits": missing})

    declared_free = set(quality.get("id_columns", [])) | set(quality.get("high_cardinality_columns", []))
    undeclared_ids = sorted({h["column"] for h in high_card if h["column"] not in declared_free})
    report.add("leakage.high_cardinality_declared",
               not undeclared_ids,
               "high-cardinality columns are declared as identifiers or free fields"
               if not undeclared_ids
               else f"high-cardinality columns are undeclared: {undeclared_ids}",
               {"undeclared": undeclared_ids, "declared": sorted(declared_free)})


def check_prediction_time(quality: dict, report: Report) -> None:
    task = quality.get("task", {})
    when = (task.get("prediction_time") or "").strip()
    report.add("timing.prediction_time_declared", bool(when),
               "prediction instant is declared" if when
               else "quality.json has no task.prediction_time")

    features = set(quality.get("features", []))
    post_hoc = set(quality.get("post_hoc_columns", []))
    overlap = sorted(features & post_hoc)
    report.add("timing.no_post_hoc_feature", not overlap,
               "no feature is documented as post-hoc" if not overlap
               else f"features documented as post-hoc: {overlap}", {"overlap": overlap})

    sources = set(quality.get("label_source_columns", []))
    source_features = sorted(features & sources)
    report.add("timing.label_source_is_not_a_feature", not source_features,
               "the label source is not a feature" if not source_features
               else f"label source used as a feature: {source_features}",
               {"source_features": source_features})

    documented = quality.get("features_documented_at")
    report.add("timing.every_feature_documented",
               documented == "prediction_time",
               f"features documented as available {documented!r}",
               {"features_documented_at": documented})


def check_units_and_frames(quality: dict, report: Report) -> None:
    measured = quality.get("measurements", [])
    missing = [entry.get("column") for entry in measured
               if not entry.get("unit") or not entry.get("frame")]
    report.add("units.measured_columns_declare_unit_and_frame",
               bool(measured) and not missing,
               f"{len(measured)} measured column(s) declare unit and frame"
               if measured and not missing
               else f"columns missing unit or frame: {missing}" if measured
               else "no measurements declared",
               {"measurements": measured})

    if quality.get("external_threshold"):
        event = quality.get("known_event") or {}
        has_event = bool(event.get("name")) and \
            event.get("expected_verdict") in ("exceeds", "below") and bool(event.get("source"))
        report.add("units.known_event_fixture_recorded", has_event,
                   f"known-event fixture recorded: {event.get('name')!r}" if has_event
                   else "an external threshold is used but no verifiable known-event fixture "
                        "is recorded",
                   {"known_event": event})
    else:
        report.add("units.known_event_fixture_recorded", True,
                   "no external threshold, so no known-event fixture is required")


def check_splits(quality: dict, report: Report, columns_by_split: dict) -> None:
    splits = quality.get("splits", {})
    windows = quality.get("split_windows", {})
    time_column = quality.get("time_column")
    keys = ["train", "eval", "holdout"]

    report.add("splits.time_column_declared", bool(time_column),
               f"split overlap is checked against {time_column!r}" if time_column
               else "quality.json must declare time_column so split overlap can be checked "
                    "from the rows")

    declared_ok = all(key in windows and isinstance(windows[key], dict) for key in keys)
    report.add("splits.machine_readable_windows", declared_ok,
               "train/eval/holdout windows are declared with start/end"
               if declared_ok
               else "quality.json must declare split_windows with per-split start/end, so the "
                    "rows can be checked against them",
               {"split_windows": windows})

    present = [key for key in keys if key in splits]
    missing_files = [key for key in keys
                     if key not in splits or not (Path(report.dataset) / splits[key]).is_file()]
    report.add("splits.files_present", not missing_files,
               "all three split files exist" if not missing_files
               else f"missing split files: {missing_files}", {"missing": missing_files})
    if missing_files or not present:
        return

    target = quality["target"]
    positive = str(quality["positive_label"])
    counts: dict[str, dict] = {}
    for key in keys:
        fieldnames, columns = columns_by_split[key]
        labels = columns.get(target, [])
        pos = sum(1 for value in labels if value == positive)
        counts[key] = {"rows": len(labels), "positives": pos, "negatives": len(labels) - pos,
                       "positive_rate": round(pos / len(labels), 6) if labels else None}

    problems = [f"{key} is empty" for key in keys if counts[key]["rows"] == 0]
    report.add("splits.non_empty", not problems,
               "every split has rows" if not problems else "; ".join(problems), counts)

    # Both classes, judged from the rows. An eval or holdout split with no negatives scores
    # a meaningless AUC, and a declaration saying otherwise must not save it.
    single_class = [f"{key} has {counts[key]['positives']} positives and "
                    f"{counts[key]['negatives']} negatives"
                    for key in ("eval", "holdout")
                    if counts[key]["positives"] == 0 or counts[key]["negatives"] == 0]
    report.add("splits.eval_and_holdout_have_both_classes", not single_class,
               "eval and holdout each contain positives and negatives"
               if not single_class else "; ".join(single_class), counts)

    declared_events = quality.get("positive_events", {})
    missing_decl = [key for key in ("eval", "holdout")
                    if not (declared_events.get(key) or {}).get("positives")
                    or not (declared_events.get(key) or {}).get("distinct_events")]
    report.add("splits.positive_events_declared", not missing_decl,
               "eval and holdout declare positives and distinct events" if not missing_decl
               else f"missing clustered counts for {missing_decl}",
               {"declared": declared_events})

    mismatched = []
    for key in ("eval", "holdout"):
        entry = declared_events.get(key) or {}
        if "positives" in entry and entry["positives"] != counts[key]["positives"]:
            mismatched.append(f"{key}: declared {entry['positives']}, rows have "
                              f"{counts[key]['positives']}")
    report.add("splits.positive_events_match_rows", not mismatched,
               "declared positive counts match the rows" if not mismatched
               else "; ".join(mismatched), {"mismatched": mismatched})

    # The clustered event count is a claim like any other, so it is recomputed from the rows.
    # An "event" is one distinct date of the declared event key among the positive rows, which
    # is the conservative reading: positives sharing a day are not independent.
    event_key = quality.get("event_key_column")
    report.add("splits.event_key_column_declared", bool(event_key),
               f"clustered events are counted by {event_key!r} (date part)" if event_key
               else "quality.json must declare event_key_column so the clustered event count "
                    "can be recomputed from the rows")
    recomputed: dict[str, int | None] = {key: None for key in keys}
    event_mismatch = []
    if event_key:
        for key in keys:
            fieldnames, columns = columns_by_split[key]
            if event_key not in columns:
                event_mismatch.append(f"{key} has no {event_key} column")
                continue
            days = {value[:10] for value, label in zip(columns[event_key], columns[target])
                    if label == positive and value}
            recomputed[key] = len(days)
            declared = (declared_events.get(key) or {}).get("distinct_events")
            if declared is not None and declared != len(days):
                event_mismatch.append(f"{key}: declared {declared} distinct events, "
                                      f"rows have {len(days)}")
        report.add("splits.distinct_events_match_rows", not event_mismatch,
                   "declared clustered event counts match the rows" if not event_mismatch
                   else "; ".join(event_mismatch),
                   {"recomputed": recomputed, "declared": declared_events})

    thin = []
    for key in ("eval", "holdout"):
        entry = declared_events.get(key) or {}
        declared_pos = entry.get("positives", counts[key]["positives"])
        events = entry.get("distinct_events") if recomputed[key] is None else recomputed[key]
        if declared_pos < MIN_EVAL_POSITIVES or (events is not None
                                                 and events < MIN_DISTINCT_EVENTS):
            thin.append(f"{key}={declared_pos} positives / {events} distinct events "
                        f"(positives threshold {MIN_EVAL_POSITIVES}, "
                        f"event threshold {MIN_DISTINCT_EVENTS})")
    report.add("splits.enough_clustered_positives", not thin,
               "eval and holdout carry enough independent positive events to score"
               if not thin else "too few independent positives: " + "; ".join(thin),
               {"thin": thin, "recomputed_events": recomputed,
                "minimums": {"positives": MIN_EVAL_POSITIVES,
                             "distinct_events": MIN_DISTINCT_EVENTS}})

    rates = [counts[key]["positive_rate"] for key in keys
             if counts[key]["positive_rate"] is not None]
    uniform = bool(rates) and all(rate in (0.0, 1.0) for rate in rates)
    report.add("splits.rates_not_uniform", not uniform,
               "positive rates are between 0 and 1" if not uniform
               else "every split is all-positive or all-negative, which is a unit or frame "
                    "red flag", {"rates": rates})

    if not time_column:
        return

    ranges = {}
    for key in keys:
        values = [v for v in columns_by_split[key][1].get(time_column, []) if v]
        ranges[key] = {"min": min(values), "max": max(values)} if values else None
    report.add("splits.actual_ranges_computed",
               all(ranges[key] for key in keys),
               "row timestamps found for every split" if all(ranges[key] for key in keys)
               else f"no {time_column} values in {[k for k in keys if not ranges[k]]}",
               {"ranges": ranges})
    if not all(ranges[key] for key in keys):
        return

    overlaps = []
    for i, left in enumerate(keys):
        for right in keys[i + 1:]:
            if ranges[left]["min"] <= ranges[right]["max"] and \
                    ranges[right]["min"] <= ranges[left]["max"]:
                overlaps.append(f"{left} [{ranges[left]['min']}..{ranges[left]['max']}] "
                                f"overlaps {right} [{ranges[right]['min']}..{ranges[right]['max']}]")
    report.add("splits.actual_ranges_disjoint", not overlaps,
               "the rows of the three splits occupy disjoint periods" if not overlaps
               else "; ".join(overlaps), {"ranges": ranges, "overlaps": overlaps})

    outside = []
    if declared_ok:
        for key in keys:
            start = windows[key].get("start")
            end = windows[key].get("end")
            if start and ranges[key]["min"] < str(start):
                outside.append(f"{key} starts {ranges[key]['min']}, before its declared "
                               f"start {start}")
            if end and ranges[key]["max"] >= str(end):
                outside.append(f"{key} reaches {ranges[key]['max']}, at or past its declared "
                               f"end {end}")
    report.add("splits.rows_within_declared_windows", not outside,
               "every row falls inside its split's declared window" if not outside
               else "; ".join(outside), {"windows": windows, "ranges": ranges})

    id_columns = quality.get("id_columns", [])
    if id_columns:
        id_column = id_columns[0]
        target = quality.get("target")
        seen: dict[str, str] = {}
        first_label: dict[tuple, object] = {}    # (split, id) -> the label first seen for it
        shared = []                    # an identifier spanning two splits: leakage
        duplicate_rows: dict[str, int] = {}      # repeats inside one split: the source's grain
        duplicate_labels: dict[tuple, set] = {}
        for key in keys:
            values = columns_by_split[key][1].get(id_column, [])
            labels = columns_by_split[key][1].get(target, []) if target else []
            for index, value in enumerate(values):
                label = labels[index] if index < len(labels) else None
                first = seen.get(value)
                if first is None:
                    seen[value] = key
                    first_label[(key, value)] = label
                elif first != key:
                    shared.append(f"{value} in {first} and {key}")
                else:
                    duplicate_rows[key] = duplicate_rows.get(key, 0) + 1
                    # Both occurrences matter: comparing only against the repeat would call a
                    # contradictory pair consistent.
                    duplicate_labels.setdefault((key, value), set()).add(
                        first_label.get((key, value)))
                    duplicate_labels[(key, value)].add(label)
        # Two different properties, deliberately checked separately. A repeated identifier
        # *inside* one split is not split leakage - it is the source having more than one row
        # per identifier - and conflating them fails a usable dataset with a message that reads
        # "... in train and train". Only a cross-split identifier is a leak.
        report.add("splits.no_cross_split_entities", not shared,
                   f"no {id_column} appears in more than one split" if not shared
                   else f"{len(shared)} identifiers span two splits: {shared[:3]}",
                   {"shared_sample": shared[:10], "shared_count": len(shared)})

        repeated = sum(duplicate_rows.values())
        tolerance = quality.get("expected_duplicate_ids")
        if tolerance is None:
            report.add("splits.duplicate_entities_within_splits", not repeated,
                       "no identifier repeats inside a split" if not repeated
                       else f"{repeated} rows repeat an identifier within a split "
                            f"{duplicate_rows}; declare expected_duplicate_ids in "
                            f"quality.json to pin a known count",
                       {"duplicate_rows": duplicate_rows})
        else:
            report.add("splits.duplicate_entities_within_splits", repeated <= tolerance,
                       f"{repeated} repeated-identifier rows within splits, at most the "
                       f"declared {tolerance}" if repeated <= tolerance
                       else f"{repeated} repeated-identifier rows exceeds the declared "
                            f"expected_duplicate_ids={tolerance}",
                       {"duplicate_rows": duplicate_rows, "declared": tolerance})

        if duplicate_labels:
            contradictory = sorted(f"{value} in {key}"
                                   for (key, value), labels in duplicate_labels.items()
                                   if len(labels) > 1)
            # This check is only meaningful against a claim. If the descriptor says the id
            # column identifies a unique entity, one label per identifier follows and a
            # contradiction is label noise. If it makes no such claim, the identifier is just
            # reused - Austin's `incident_number` carries two *different* events hours apart,
            # with different sectors and different labels - and the right thing is to measure
            # the count and put it in the report rather than to refuse the dataset for a
            # property the source does not claim to have.
            claims_entity_key = quality.get("id_columns_are_entity_keys") is True
            if claims_entity_key:
                report.add("splits.repeated_identifiers_carry_one_label", not contradictory,
                           "each repeated identifier carries one label, as declared"
                           if not contradictory else
                           f"{len(contradictory)} repeated identifiers carry more than one "
                           f"label while id_columns_are_entity_keys is declared true: "
                           f"{contradictory[:3]}",
                           {"sample": contradictory[:10], "count": len(contradictory)})
            else:
                report.add("splits.repeated_identifiers_carry_one_label", True,
                           f"{len(contradictory)} of {len(duplicate_labels)} repeated "
                           f"identifiers carry more than one label; the descriptor does not "
                           f"claim id_columns_are_entity_keys, so this is recorded as a source "
                           f"property: {contradictory[:3]}",
                           {"sample": contradictory[:10], "count": len(contradictory),
                            "repeated_identifiers": len(duplicate_labels),
                            "claimed_entity_key": False})


def check_runner(dataset: Path, quality: dict, report: Report,
                 columns_by_split: dict) -> None:
    splits = quality.get("splits", {})
    layout_ok = splits.get("holdout", "").startswith("private/") and \
        splits.get("train", "").startswith("public/") and \
        splits.get("eval", "").startswith("public/")
    report.add("runner.layout", layout_ok,
               "holdout is private and train/eval are public" if layout_ok
               else f"unexpected layout: {splits}")

    meta_path = dataset / "meta.json"
    if not meta_path.is_file():
        report.add("runner.meta_json", False, "meta.json is missing")
        return
    meta = json.loads(meta_path.read_text())
    required = ["target", "positive_label", "id_columns", "columns", "rows", "positive_rate"]
    missing = [key for key in required if key not in meta]
    report.add("runner.meta_json_keys", not missing,
               "meta.json carries the keys the runner reads" if not missing
               else f"meta.json missing {missing}", {"keys": sorted(meta)})
    if missing:
        return

    target = meta["target"]
    problems = []
    if meta["positive_label"] != quality["positive_label"]:
        problems.append("meta positive_label disagrees with quality.json")
    if target != quality["target"]:
        problems.append("meta target disagrees with quality.json")
    if not set(meta["id_columns"]) <= set(meta["columns"]):
        problems.append("id_columns are not a subset of columns")
    for key in ("train", "eval", "holdout"):
        fieldnames, _ = columns_by_split[key]
        if target not in fieldnames:
            problems.append(f"{key} lacks the target column")
        if list(meta["columns"]) != fieldnames:
            problems.append(f"{key} header differs from meta columns")
    report.add("runner.meta_matches_files", not problems,
               "meta.json agrees with the split files" if not problems
               else "; ".join(problems), {"problems": problems})

    counts_ok, detail = True, "meta rows and rates match the files"
    for key in ("train", "eval", "holdout"):
        labels = columns_by_split[key][1].get(target, [])
        pos = sum(1 for value in labels if value == str(meta["positive_label"]))
        rate = pos / len(labels) if labels else 0.0
        if meta["rows"].get(key) != len(labels):
            counts_ok, detail = False, f"{key} row count mismatch"
        if meta["positive_rate"].get(key) is not None and \
                abs(meta["positive_rate"][key] - rate) > 1e-6:
            counts_ok, detail = False, f"{key} positive rate mismatch"
    report.add("runner.meta_counts_match_files", counts_ok, detail)

    id_cols = set(meta["id_columns"])
    id_feature_ok = not (id_cols & set(quality.get("features", [])))
    report.add("runner.id_columns_are_not_features", id_feature_ok,
               "declared identifiers are not also listed as features" if id_feature_ok
               else f"identifiers listed as features: {sorted(id_cols & set(quality.get('features', [])))}")


def qualify(dataset: Path) -> Report:
    report = Report(dataset)
    quality_path = dataset / "quality.json"
    if not quality_path.is_file():
        report.add("descriptor", False, f"quality.json not found in {dataset}")
        return report
    quality = json.loads(quality_path.read_text())
    report.add("descriptor", True,
               f"quality.json loaded for {quality.get('name', dataset.name)!r}")

    splits = quality.get("splits", {})
    columns_by_split: dict[str, tuple] = {}
    for key in ("train", "eval", "holdout"):
        relative = splits.get(key)
        path = dataset / relative if relative else None
        if path and path.is_file():
            columns_by_split[key] = read_columns(path)

    for key in ("train", "eval", "holdout"):
        relative = splits.get(key)
        path = dataset / relative if relative else None
        if path and path.is_file():
            report.artifact[key] = {"file": relative, "sha256": sha256_of(path),
                                    "bytes": path.stat().st_size}
    meta_path = dataset / "meta.json"
    if meta_path.is_file():
        report.artifact["meta.json"] = {"file": "meta.json", "sha256": sha256_of(meta_path),
                                        "bytes": meta_path.stat().st_size}
    report.artifact["quality.json"] = {"file": "quality.json",
                                       "sha256": sha256_of(quality_path),
                                       "bytes": quality_path.stat().st_size}
    report.artifact["artifact_version"] = {
        "digest": hashlib.sha256(
            "".join(sorted(f"{key}:{value['sha256']}"
                           for key, value in report.artifact.items()
                           if isinstance(value, dict) and "sha256" in value)).encode()
        ).hexdigest(),
        "components": sorted(key for key, value in report.artifact.items()
                             if isinstance(value, dict) and "sha256" in value),
    }

    check_leakage(dataset, quality, report, columns_by_split)
    check_prediction_time(quality, report)
    check_units_and_frames(quality, report)
    check_splits(quality, report, columns_by_split)
    check_runner(dataset, quality, report, columns_by_split)
    return report


def accept(report_path: Path, dataset: Path) -> int:
    """Downstream gate: a passing report whose artifact hashes still match the files."""
    if not report_path.is_file():
        print(f"ACCEPT FAILED: no qualification report at {report_path}")
        return 1
    report = json.loads(report_path.read_text())
    if report.get("gate_version") != GATE_VERSION:
        print(f"ACCEPT FAILED: report was produced by gate {report.get('gate_version')}, "
              f"this gate is {GATE_VERSION}")
        return 1
    if not report.get("ok"):
        print("ACCEPT FAILED: the qualification report did not pass. Failed checks: "
              + ", ".join(report.get("failed_checks", [])))
        return 1
    recorded = report.get("artifact", {})
    problems = []
    for key in ("train", "eval", "holdout", "meta.json", "quality.json"):
        entry = recorded.get(key)
        if not entry:
            problems.append(f"{key} is missing from the report")
            continue
        path = dataset / entry["file"]
        if not path.is_file():
            problems.append(f"{entry['file']} is missing from {dataset}")
            continue
        digest = sha256_of(path)
        if digest != entry["sha256"]:
            problems.append(f"{entry['file']} has changed since qualification "
                            f"({digest[:12]} != {entry['sha256'][:12]})")
    if problems:
        print("ACCEPT FAILED: the artifact does not match the qualified version")
        for problem in problems:
            print(" -", problem)
        return 1
    print(f"ACCEPTED: {dataset} matches the qualified artifact "
          f"{recorded['artifact_version']['digest'][:16]}")
    return 0


SELFTEST_EXPECTATIONS = {
    "broken": {
        "expected_ok": False,
        "must_fail": {
            "leakage.answer_source_absent",
            "leakage.no_single_column_determines_the_target",
            "timing.no_post_hoc_feature",
            "units.known_event_fixture_recorded",
            "runner.layout",
        },
    },
    "broken-overlap": {
        "expected_ok": False,
        "must_fail": {
            "splits.actual_ranges_disjoint",
            "splits.rows_within_declared_windows",
        },
    },
    "broken-single-class": {
        "expected_ok": False,
        "must_fail": {
            "splits.eval_and_holdout_have_both_classes",
        },
    },
    "broken-duplicates": {
        "expected_ok": False,
        "must_fail": {
            # The count is not declared, so a repeat is refused rather than tolerated.
            "splits.duplicate_entities_within_splits",
        },
    },
    "broken-duplicate-labels": {
        "expected_ok": False,
        "must_fail": {
            # The descriptor claims a unique entity key, so contradictory labels are noise.
            "splits.repeated_identifiers_carry_one_label",
        },
    },
    # The same rows without that claim, which is the real Austin case: measured and accepted.
    "documented-repeats": {"expected_ok": True, "must_fail": set()},
    "corrected": {"expected_ok": True, "must_fail": set()},
}


def selftest(fixtures_root: Path) -> int:
    failures = []
    for name, expectation in SELFTEST_EXPECTATIONS.items():
        dataset = fixtures_root / name
        if not dataset.is_dir():
            failures.append(f"{name}: fixture directory missing at {dataset}")
            continue
        report = qualify(dataset)
        failed_checks = {result["check"] for result in report.results if not result["ok"]}
        print(f"--- fixture {name}: ok={report.ok} (expected {expectation['expected_ok']})")
        print(report.render())
        if report.ok != expectation["expected_ok"]:
            failures.append(f"{name}: checker said ok={report.ok}, expected "
                            f"{expectation['expected_ok']}")
        unfulfilled = expectation["must_fail"] - failed_checks
        if unfulfilled:
            failures.append(f"{name}: expected these checks to fail but they passed: "
                            f"{sorted(unfulfilled)}")
        print()
    if failures:
        print("SELFTEST FAILED")
        for failure in failures:
            print(" -", failure)
        return 1
    print("SELFTEST PASSED: every broken fixture is rejected with the expected checks and "
          "the corrected fixture is accepted.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Qualify a constructed dataset")
    parser.add_argument("dataset", nargs="?", help="dataset directory to check")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument("--report", help="write the JSON report to this path")
    parser.add_argument("--accept", metavar="REPORT",
                        help="verify a report and its artifact hashes against the dataset")
    parser.add_argument("--selftest", action="store_true",
                        help="check every shipped fixture pair")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest(Path(__file__).resolve().parent.parent / "fixtures")
    if not args.dataset:
        parser.error("a dataset directory is required unless --selftest is used")

    if args.accept:
        return accept(Path(args.accept), Path(args.dataset))

    report = qualify(Path(args.dataset))
    payload = report.as_dict()
    if args.report:
        Path(args.report).write_text(json.dumps(payload, indent=1) + "\n")
    if args.json:
        print(json.dumps(payload, indent=1))
    else:
        print(report.render())
        print()
        print(f"artifact version: {report.artifact['artifact_version']['digest'][:16]}")
        print("QUALIFICATION PASSED" if report.ok else "QUALIFICATION FAILED")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
