# Data dictionary

Every file in every split has the same 12 columns, in this order.

| # | column | role | available at prediction time? | notes |
|---|---|---|---|---|
| 1 | `incident_number` | identifier (carry) | yes | The call's number **as recorded**. Not unique: 24 of 1,049,636 rows share a number with another row, and those pairs are different events (see below). Never a feature. |
| 2 | `response_datetime` | timestamp (carry) | — | The moment the call-taker's dispatch screen opened. Defines the prediction instant and the temporal split. Declared high-cardinality; never a feature. |
| 3 | `incident_type` | feature | yes | Coarse call classification known at dispatch. |
| 4 | `sector` | feature | yes | Austin police sector (patrol geography). |
| 5 | `council_district` | feature | yes | City council district. |
| 6 | `geoid` | feature | yes | Census GEOID of the call location. High-cardinality; the benchmark's baseline drops string columns over 1000 levels, so it may be dropped by that baseline. |
| 7 | `blkgpnm` | feature | yes | Census block group name. High-cardinality, same caveat as `geoid`. |
| 8 | `response_day_of_week` | feature | yes | Day of week of `response_datetime`. Derived from the timestamp, which is known at dispatch. |
| 9 | `response_hour` | feature | yes | Hour of `response_datetime`. Known at dispatch for the same reason. |
| 10 | `initial_problem_description` | feature | yes | Free text as first recorded. High-cardinality; declared as a free field rather than an identifier. |
| 11 | `initial_problem_category` | feature | yes | Category as first recorded. |
| 12 | `late` | **target** | — | `1` if `response_time > 1200` else `0`. |

`response_time` — the portal column the label is derived from — is **deliberately absent from
every split file**. It is the answer, so shipping it would hand the model the label.

## Excluded columns: present in the source, absent from every file

Each of these is either the label's source or determined *after* the prediction instant. They
are excluded because they are post-hoc, not because they are uninformative — several are
strongly predictive, which is exactly why they must not be features.

| column | why it is excluded |
|---|---|
| `response_time` | The label's source. Seconds, begins when the call was answered. |
| `first_unit_arrived_datetime` | After the outcome. |
| `call_closed_datetime` | After the outcome. |
| `priority_level` | Documented as assigned when the first officer arrives. |
| `mental_health_flag` | Derivable from the final problem description or disposition. |
| `final_problem_description` | Assignment happens after the call is dispatched. |
| `final_problem_category` | Same as above. |
| `call_disposition_description` | Written after the call closes. |
| `number_of_units_arrived` | After the outcome. |
| `unit_time_on_scene` | After the outcome. |
| `report_written_flag` | After the outcome. |
| `officer_injured_killed_count` | After the outcome. |
| `subject_injured_killed_count` | After the outcome. |
| `other_injured_killed_count` | After the outcome. |

## Splits

Temporal, by `response_datetime`, with no random component:

| split | file | predicate |
|---|---|---|
| train | `public/train.csv` | `response_datetime < '2025-01-01T00:00:00.000'` |
| eval | `public/eval.csv` | `>= '2025-01-01T00:00:00.000'` and `< '2026-01-01T00:00:00.000'` |
| holdout | `private/holdout.csv` | `>= '2026-01-01T00:00:00.000'` |

## Known data properties

- **Repeated incident numbers.** 24 incident numbers appear twice. All 24 pairs sit inside a
  single split, so no identifier spans a split boundary. Of the 24, **4 carry different
  labels**, because the two rows are different events sharing a number — for example
  `230990471` is an "Alarms"/Baker call at 07:33 with a 618-second response and an
  "Other"/Frank call at 16:38 with a 6,164-second response. The dataset does not claim
  `incident_number` identifies a unique entity; the count is declared in `quality.json` as
  `expected_duplicate_ids`.
- **Unlabelled rows are excluded by the query.** The extraction filters on
  `response_time IS NOT NULL`, because a null label cannot be trained on. Measured: **0 rows** in
  the three shipped windows were dropped after retrieval, so the exclusion is upstream of the
  counts above.
- **No imputation.** Missing values in feature columns are left as they are; the benchmark's
  `train.py` handles unseen categorical levels by mapping them to NaN.
- **The label's clock starts before the prediction instant.** `response_time` begins when the call
  was answered, which is earlier than `response_datetime`. Measured over 2,000 rows: median offset
  **−57 s** (p05 −206 s, p95 0 s, range −468 s … +6,041 s). Reproduce with
  `code/measure_clock_offset.py`. The window between the prediction instant and the start of the
  measured clock is small, but it is not zero, and every model on this dataset inherits it.
