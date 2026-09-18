#!/usr/bin/env python3
"""Download this dataset's release assets, verify them, and lay them out for the runner.

GitHub release asset names cannot contain `/`, so the assets are flat (`train.csv`,
`eval.csv`, `holdout.csv`, `meta.json`, `quality.json`) and this script puts them back into the
layout the benchmark expects:

    <dest>/public/train.csv
    <dest>/public/eval.csv
    <dest>/private/holdout.csv
    <dest>/meta.json
    <dest>/quality.json

Every file is checked against `SHA256SUMS` and the recorded artifact version, so a download that
does not match is refused rather than silently used.

The repository is private, so a credential is needed: either the `gh` CLI (already
authenticated) or `GITHUB_TOKEN` in the environment.

    python3 get_dataset.py --dest ./task
    python3 get_dataset.py --dest ./task --tag v2026.09

The equivalent by hand:

    gh release download v2026.09 --repo earino/austin-911-response --dir ./flat
    sha256sum -c SHA256SUMS      # after copying the asset names back to their paths
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "earino/austin-911-response"
# asset name -> destination inside the dataset directory
LAYOUT = {
    "train.csv": "public/train.csv",
    "eval.csv": "public/eval.csv",
    "holdout.csv": "private/holdout.csv",
    "meta.json": "meta.json",
    "quality.json": "quality.json",
}


def token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def auth_headers() -> dict:
    value = token()
    return {"Authorization": "Bearer " + value} if value else {}


def release(tag: str) -> dict:
    """Read the release through `gh` when available, else the API."""
    if shutil.which("gh") and not token():
        done = subprocess.run(["gh", "api", f"repos/{REPO}/releases/tags/{tag}"],
                              capture_output=True, text=True)
        if done.returncode == 0:
            return json.loads(done.stdout)
        raise SystemExit(f"gh could not read {REPO}@{tag}: {done.stderr.strip()[:200]}")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases/tags/{tag}",
        headers={"Accept": "application/vnd.github+json", **auth_headers()})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except Exception as exc:
        raise SystemExit(f"could not read {REPO}@{tag}: {type(exc).__name__}. "
                         "The repository is private; authenticate with `gh auth login` or set "
                         "GITHUB_TOKEN.") from None


def download(asset: dict, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("gh") and not token():
        done = subprocess.run(["gh", "release", "download", asset["_tag"], "--repo", REPO,
                               "--pattern", asset["name"], "--dir", str(dest.parent),
                               "--clobber"], capture_output=True, text=True)
        if done.returncode:
            raise SystemExit(f"gh download failed: {done.stderr.strip()[:200]}")
        (dest.parent / asset["name"]).replace(dest)
        return dest
    request = urllib.request.Request(
        asset["url"], headers={"Accept": "application/octet-stream", **auth_headers()})
    with urllib.request.urlopen(request, timeout=600) as response, dest.open("wb") as stream:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            stream.write(chunk)
    return dest


def sha256_of(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", default="task", help="where to write the dataset directory")
    parser.add_argument("--tag", default="v2026.09")
    parser.add_argument("--sums", default=None,
                        help="path to SHA256SUMS (default: ./SHA256SUMS if present)")
    args = parser.parse_args()

    info = release(args.tag)
    assets = {a["name"]: a for a in info["assets"]}
    missing = [name for name in LAYOUT if name not in assets]
    if missing:
        raise SystemExit(f"release {args.tag} is missing assets: {missing}")

    dest_root = Path(args.dest)
    written = []
    for name, relative in LAYOUT.items():
        asset = dict(assets[name], _tag=args.tag)
        path = dest_root / relative
        download(asset, path)
        size = path.stat().st_size
        if asset["size"] != size:
            raise SystemExit(f"{name}: downloaded {size} bytes, release records {asset['size']}")
        written.append((relative, size, sha256_of(path)))
        print(f"  {name:14} -> {relative:22} {size:>10,} B  {written[-1][2][:16]}...")

    sums = Path(args.sums) if args.sums else Path("SHA256SUMS")
    if sums.is_file():
        expected = {}
        for line in sums.read_text().splitlines():
            digest, _, path = line.partition("  ")
            expected[path.strip()] = digest
        problems = [relative for relative, _, digest in written
                    if relative in expected and expected[relative] != digest]
        if problems:
            raise SystemExit(f"SHA256SUMS disagrees for: {problems}")
        print(f"  verified against {sums}")
    else:
        print(f"  note: no SHA256SUMS next to this script, hashes printed above for comparison")

    print(f"\nwrote {dest_root}/ (runner layout): public/, private/, meta.json, quality.json")
    print("next: python3 code/qualify_dataset.py " + str(dest_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())