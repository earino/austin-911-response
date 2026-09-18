#!/usr/bin/env python3
"""Materialize the runner's task directory from the extract.

Mirrors `bench/workdir.py` in the harness benchmark:

  * the runner's own `train.py`, `validate.py` and `validate.sh` are copied in unmodified
    (run.sh does the copy; they are bundled verbatim and their hashes are recorded);
  * `task.json` carries exactly the keys `bench/workdir.py` writes -
    name, description, target, positive_label, id_columns, split, columns, rows;
  * `data/train.csv` and `data/eval.csv` come from the dataset's **public** split.

The private holdout is deliberately **never** copied into a workdir, exactly as the benchmark
documents ("NEVER copied into a workdir; used only by `bench eval`"). Nothing here scores it.

Usage: materialize.py <extract-dir> <workdir>
"""
import json
import shutil
import sys
from pathlib import Path

# The keys bench/workdir.py puts in the task.json an agent cell receives.
TASK_KEYS = ("name", "description", "target", "positive_label", "id_columns", "split",
             "columns", "rows")


def main() -> int:
    extract, workdir = Path(sys.argv[1]), Path(sys.argv[2])
    meta = json.loads((extract / "meta.json").read_text())
    missing = [key for key in TASK_KEYS if key not in meta]
    if missing:
        print(f"meta.json lacks keys the runner's task.json needs: {missing}", file=sys.stderr)
        return 1

    (workdir / "data").mkdir(parents=True, exist_ok=True)
    task = {key: meta[key] for key in TASK_KEYS}
    (workdir / "task.json").write_text(json.dumps(task, indent=2) + "\n")
    for name in ("train.csv", "eval.csv"):
        source = extract / "public" / name
        if not source.is_file():
            print(f"public split missing: {source}", file=sys.stderr)
            return 1
        shutil.copyfile(source, workdir / "data" / name)

    print(f"  task.json: target={task['target']} positive_label={task['positive_label']!r} "
          f"id_columns={task['id_columns']} rows={task['rows']}")
    print(f"  data/: train.csv + eval.csv copied; the private holdout was NOT copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())