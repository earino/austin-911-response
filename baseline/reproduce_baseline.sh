#!/bin/sh
# Reproduce the recorded baseline: the benchmark's own train.py and validate.py, unmodified,
# against this dataset.
#
#   sh baseline/reproduce_baseline.sh [dataset-dir]      (default: ./task)
#
# <dataset-dir> is what get_dataset.py produces: public/, private/, meta.json, quality.json.
# The private holdout is deliberately NOT copied into the working directory - the contract scores
# train and eval only, and the holdout stays out of any workdir.
#
# Task materialization follows the benchmark's bench/workdir.py: task.json carries the keys the
# runner reads, and data/train.csv + data/eval.csv come from the public split.
set -eu

DATASET=$(cd "${1:-task}" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
WORK="${WORK:-/tmp/austin-baseline-task}"

if [ ! -f "$DATASET/meta.json" ]; then
    echo "no meta.json in $DATASET - run get_dataset.py first" >&2
    exit 1
fi

rm -rf "$WORK"
mkdir -p "$WORK"
cp "$HERE/train.py" "$HERE/validate.py" "$HERE/validate.sh" "$WORK/"
python3 "$HERE/../code/materialize.py" "$DATASET" "$WORK"

if ! python3 -c "import pandas, numpy, xgboost, sklearn" 2>/dev/null; then
    echo "installing the benchmark's declared dependency ranges ..."
    python3 -m pip install --quiet "pandas>=2.2,<3" "numpy>=1.26" "xgboost>=3.0" "scikit-learn>=1.5"
fi

cd "$WORK"
echo "== contract: python train.py =="
python3 train.py
echo "== contract: sh validate.sh =="
sh validate.sh
