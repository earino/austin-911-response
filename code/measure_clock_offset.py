#!/usr/bin/env python3
"""Measure how the portal's `response_time` relates to `response_datetime`.

The dataset predicts from `response_datetime`, but the label comes from `response_time`. If
those two clocks started at the same instant, then

    (first_unit_arrived_datetime - response_datetime) == response_time

would hold exactly. It does not, and this script measures by how much, so the dataset card can
state the offset as a measurement instead of an assumption.

Reported as `delta_seconds = (first_unit_arrived_datetime - response_datetime) - response_time`:

  * delta < 0  -> `response_time` is longer than dispatch-to-arrival, so its clock starts BEFORE
                  `response_datetime` (consistent with starting when the call was answered);
  * delta > 0  -> `response_time` is shorter, so its clock starts after `response_datetime`;
  * delta == 0 -> the two clocks agree for that row.

Sampling is deterministic (`$order=:id`, first N rows) so a re-run on an unchanged catalogue
returns the same rows. It is a bounded sample, not the full series: the count of rows is small
on purpose, and the method is stated rather than the sample being presented as exhaustive.

Usage: python3 measure_clock_offset.py [rows] [--json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime

BASE = "https://datahub.austintexas.gov/resource/e687-fx2y.json"
HEADERS = {"User-Agent": "austin-911-response-dataset clock-offset measurement"}
WHERE = ("response_time IS NOT NULL AND first_unit_arrived_datetime IS NOT NULL "
         "AND response_datetime IS NOT NULL")


def fetch(rows: int, page: int = 2000) -> list[dict]:
    out, offset = [], 0
    while len(out) < rows:
        want = min(page, rows - len(out))
        params = {"$select": ":id,incident_number,response_datetime,response_time,"
                             "first_unit_arrived_datetime",
                  "$where": WHERE, "$order": ":id", "$limit": str(want), "$offset": str(offset)}
        url = BASE + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS),
                                    timeout=120) as response:
            batch = json.load(response)
        if not batch:
            break
        out.extend(batch)
        offset += len(batch)
    return out


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", nargs="?", type=int, default=2000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    deltas = []
    for row in fetch(args.rows):
        try:
            dispatched = parse(row["response_datetime"])
            arrived = parse(row["first_unit_arrived_datetime"])
            reported = int(row["response_time"])
        except (KeyError, TypeError, ValueError):
            continue
        deltas.append((arrived - dispatched).total_seconds() - reported)

    if not deltas:
        print("no usable rows returned", file=sys.stderr)
        return 1
    ordered = sorted(deltas)

    def quantile(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]

    summary = {
        "method": {"where": WHERE, "order": ":id", "rows_requested": args.rows,
                   "rows_measured": len(deltas),
                   "delta_seconds_definition":
                       "(first_unit_arrived_datetime - response_datetime) - response_time"},
        "median": statistics.median(deltas),
        "mean": round(statistics.fmean(deltas), 3),
        "min": min(deltas),
        "max": max(deltas),
        "p05": quantile(0.05),
        "p95": quantile(0.95),
        "within_one_second": sum(1 for d in deltas if abs(d) <= 1),
        "negative": sum(1 for d in deltas if d < 0),
        "positive": sum(1 for d in deltas if d > 0),
        "exact_zero": sum(1 for d in deltas if d == 0),
    }
    if args.json:
        print(json.dumps(summary, indent=2))
        return 0
    print(f"measured {summary['method']['rows_measured']} rows (deterministic order by :id)")
    print(f"  delta = (arrival - response_datetime) - response_time, in seconds")
    print(f"  median {summary['median']}, mean {summary['mean']}, "
          f"range {summary['min']} .. {summary['max']}")
    print(f"  p05 {summary['p05']}, p95 {summary['p95']}")
    print(f"  negative (response_time starts earlier): {summary['negative']}")
    print(f"  positive (starts later): {summary['positive']}, exact zero: {summary['exact_zero']}")
    print(f"  within one second of agreement: {summary['within_one_second']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())