#!/usr/bin/env python3
"""Portable static renderer, copied into each managed repo. Python stdlib only; no network."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

VERSION = "1"


def canonical(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, label):
    if not url.startswith("https://"):
        raise ValueError("External links must be HTTPS")
    return f'<a href="{esc(url)}">{esc(label)}</a>'


def document(title, body, config, preview=False):
    notice = '<aside class="preview">Review build · publication has not been verified.</aside>' if preview else ""
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · {esc(config['title'])}</title><style>
:root{{color-scheme:light;--ink:#18352d;--muted:#53675f;--line:#ced7cf;--paper:#f6f5ef;--accent:#19694e}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:17px/1.65 system-ui,sans-serif}}
a{{color:var(--accent);text-underline-offset:4px}}a:focus-visible{{outline:3px solid #d4a52d;outline-offset:4px}}
header,main,footer{{max-width:1100px;margin:auto;padding:28px}}header{{display:flex;justify-content:space-between;border-bottom:1px solid var(--line)}}
header a{{font-weight:700}}main{{padding-top:55px}}h1{{font:clamp(2.2rem,6vw,4rem)/1.08 Georgia,serif;max-width:900px;margin:10px 0 24px;letter-spacing:-.035em}}
h2{{font:2rem/1.2 Georgia,serif;margin-top:48px}}h3{{margin-top:0}}p{{max-width:80ch}}.intro{{font-size:1.2rem;color:var(--muted)}}
.eyebrow{{font-size:.8rem;text-transform:uppercase;letter-spacing:.14em;color:var(--muted)}}.links{{display:flex;flex-wrap:wrap;gap:12px 25px;margin:25px 0}}
.card{{border:1px solid var(--line);border-radius:6px;padding:28px;background:#fffdfa;margin:20px 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}}
.stat{{border-top:2px solid var(--accent);padding:15px 0}}.stat strong{{display:block;font-size:1.8rem}}table{{border-collapse:collapse;width:100%;text-align:left}}
th,td{{border-bottom:1px solid var(--line);padding:12px 10px;vertical-align:top}}th{{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}}
.scroll{{overflow-x:auto}}code{{font-size:.84rem;overflow-wrap:anywhere}}pre{{padding:20px;background:#e9eee7;overflow-x:auto;border-radius:5px}}
.preview{{background:#ffedb7;padding:14px 28px;text-align:center}}footer{{border-top:1px solid var(--line);color:var(--muted);font-size:.9rem;margin-top:50px}}
details{{margin:12px 0}}summary{{cursor:pointer}}@media(max-width:600px){{header,main,footer{{padding:20px}}h1{{margin-top:20px}}.card{{padding:20px}}}}
</style></head><body>{notice}<header>{link(config['catalog_url'],config['title'])}<span>Reproducible prediction tasks</span></header>
<main>{body}</main><footer>Sources, construction and measured baselines accompany every dataset. Public holdouts stay outside evaluated agents’ workspaces.</footer></body></html>'''


def navigation(record):
    u = record["urls"]
    return '<nav class="links" aria-label="Dataset destinations">' + "".join(
        link(u[key], title) for key, title in (("github_release", "GitHub release"),
                                             ("huggingface_version", "Hugging Face"),
                                             ("catalog", "All datasets"))) + "</nav>"


def dataset_body(r):
    rows = sum(s["rows"] for s in r["splits"].values())
    split_rows = "".join(f'<tr><th scope="row">{esc(k)}</th><td>{s["rows"]:,}</td><td>' +
                         (f'{s["positives"]:,} ({s["positives"]/s["rows"]:.2%})' if "positives" in s else "—") +
                         '</td></tr>' for k, s in r["splits"].items())
    asset_rows = "".join(f'<tr><td>{link(a["download"], name)}</td><td>{a["bytes"]:,}</td>'
                         f'<td><code>{esc(a["sha256"])}</code></td></tr>' for name, a in r["assets"].items())
    terms = r["licenses"]
    metrics = "".join(f'<div class="stat"><strong>{esc(v)}</strong>{esc(k)}</div>'
                      for k, v in r["baseline"]["metrics"].items())
    docs = "".join(link(r["urls"]["github"] + '/blob/' + r["release_tag"] + '/' + path, label) for path, label in (
        ("DATA_DICTIONARY.md", "Data dictionary"), ("REPRODUCE.md", "Reproduction"),
        ("VERIFICATION.md", "Verification"), ("LICENSE.md", "Licence and attribution")))
    return f'''<div class="eyebrow">{esc(r['domain'])} · {esc(r['task_type'])} · {esc(r['release_tag'])}</div>
<h1>{esc(r['title'])}</h1><p class="intro">{esc(r['summary'])}</p>{navigation(r)}
<div class="grid"><div class="stat"><strong>{rows:,}</strong>rows</div><div class="stat"><strong>{len(r['splits'])}</strong>documented splits</div>{metrics}</div>
<h2>About this release</h2>{''.join('<p>'+esc(p)+'</p>' for p in r['post']['paragraphs'])}
<h2>Splits</h2><div class="scroll"><table><thead><tr><th>Split</th><th>Rows</th><th>Positive labels</th></tr></thead><tbody>{split_rows}</tbody></table></div>
<h2>Qualification and baseline</h2><p>{esc(r['qualification']['result'])} Gate {esc(r['qualification']['gate_version'])}.</p><p>{esc(r['baseline']['scope'])}</p>
<h2>Use this version</h2><pre><code>{esc('from datasets import load_dataset' + chr(10) + 'ds = load_dataset(' + repr(r['hf_repository']) + ', revision=' + repr(r['release_tag']) + ')')}</code></pre>
<p>The version links and checksums identify this artifact. Exclude the labelled holdout from the agent's workspace when running an evaluation.</p>
<nav class="links" aria-label="Documentation">{docs}</nav>
<h2>Files and checksums</h2><div class="scroll"><table><thead><tr><th>Download</th><th>Bytes</th><th>SHA-256</th></tr></thead><tbody>{asset_rows}</tbody></table></div>
<p>Artifact <code>{esc(r['artifact_version'])}</code></p>
<h2>Limitations</h2><ul>{''.join('<li>'+esc(p)+'</li>' for p in r['limitations'])}</ul>
<h2>Source and terms</h2><p>{link(r['source']['url'],r['source']['name'])}</p><p>{esc(terms['attribution'])}</p>
<p>Source: {esc(terms['source_data'])}. Compilation: {esc(terms['data_compilation'])}. Code and documentation: {esc(terms['code'])}.</p>
<p>{esc(terms['compilation_scope'])}</p><h3>Suggested citation</h3><p>{esc(terms['citation'])}</p>'''


def render(config, records, preview=False, editions=()):
    """Pure rendering: no filesystem, clock, credentials, remote requests or private metadata."""
    if config.get("schema_version") != 1 or config.get("kind") not in ("catalog", "dataset"):
        raise ValueError("Unsupported renderer configuration")
    records = sorted(records, key=lambda r: (r["release_date"], r["release_tag"], r["dataset"]), reverse=True)
    seen = set()
    for r in records:
        copy = dict(r)
        checksum = copy.pop("record_sha256", None)
        if r.get("schema_version") != 1 or checksum != hashlib.sha256(canonical(copy).encode()).hexdigest():
            raise ValueError("Release record digest or schema does not match")
        if type(r.get("site_revision")) is not int or r["site_revision"] < 1:
            raise ValueError("Website edition must be a positive integer")
        for value in (r["dataset"], r["release_tag"]):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
                raise ValueError("Unsafe dataset or version path")
        key = (r["dataset"], r["release_tag"])
        if key in seen:
            raise ValueError("Duplicate release record")
        seen.add(key)
    if not records:
        raise ValueError("A website needs at least one approved release record")
    files = {".nojekyll": ""}
    if config["kind"] == "dataset":
        if len({r["dataset"] for r in records}) != 1:
            raise ValueError("A dataset site may only contain one dataset")
        latest = records[0]
        history = '<h2>Versions</h2><ul>' + "".join('<li>' + link(r["urls"]["version"], r["release_tag"]) + '</li>' for r in records) + '</ul>'
        files["index.html"] = document(latest["title"], dataset_body(latest) + history, config, preview)
        files["release.json"] = canonical(latest)
        for r in records:
            prefix = 'versions/' + r["release_tag"] + '/'
            files[prefix + "index.html"] = document(r["title"], dataset_body(r) + history, config, preview)
            files[prefix + "release.json"] = canonical(r)
    else:
        latest = {}
        for r in records:
            latest.setdefault(r["dataset"], r)
        cards = "".join(f'<article class="card"><div class="eyebrow">{esc(r["domain"])} · {esc(r["release_tag"])}</div>'
                        f'<h2>{link(r["urls"]["version"],r["title"])}</h2><p>{esc(r["summary"])}</p>{navigation(r)}</article>' for r in latest.values())
        posts = []
        for r in records:
            url = config["catalog_url"] + 'releases/' + r["dataset"] + '/' + r["release_tag"] + '/'
            posts.append(f'<li>{esc(r["release_date"])} — {link(url,r["post"]["title"])}</li>')
            body = f'<div class="eyebrow">Release notes · {esc(r["release_date"])}</div><h1>{esc(r["post"]["title"])}</h1>'
            body += ''.join('<p>' + esc(p) + '</p>' for p in r["post"]["paragraphs"])
            body += link(r["urls"]["version"], 'Explore the dataset') + navigation(r)
            files[f'releases/{r["dataset"]}/{r["release_tag"]}/index.html'] = document(r["post"]["title"], body, config, preview)
        body = f'<div class="eyebrow">An ongoing collection</div><h1>New data.<br>Useful prediction tasks.</h1><p class="intro">{esc(config["description"])}</p>'
        body += '<h2>Datasets</h2>' + cards + '<h2>Release archive</h2><ul>' + ''.join(posts) + '</ul>'
        files["index.html"] = document(config["title"], body, config, preview)
        files["catalog.json"] = canonical({"schema_version": 1, "releases": records})
    files["site-build.json"] = canonical({"renderer_version": VERSION, "preview": preview,
        "releases": [{key: r[key] for key in ("dataset", "release_tag", "artifact_version", "record_sha256")} for r in records]})
    for r in editions:
        base = (f'versions/{r["release_tag"]}/editions/' if config["kind"] == "dataset" else
                f'releases/{r["dataset"]}/{r["release_tag"]}/editions/') + str(r["site_revision"]) + '/'
        # Validate and render each immutable edition through the same contract.
        historical = render(config, [r], preview=preview)
        files[base + "release.json"] = canonical(r)
        files[base + "index.html"] = historical["index.html"]
    return files


def write_output(out, files):
    out = Path(out)
    marker = out / ".dataset-factory-site-output"
    if out.is_symlink() or any(p.is_symlink() for p in (out, *out.parents)):
        raise ValueError("Output path must not pass through a symlink")
    if out.exists() and (not out.is_dir() or ((out / '.git').exists()) or (any(out.iterdir()) and not marker.is_file())):
        raise ValueError("Refusing to overwrite a non-owned output directory")
    out.mkdir(parents=True, exist_ok=True)
    marker.write_text("dataset-factory site output v1\n")
    for relative, text in files.items():
        path = out / relative
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError("Output contains a symlink")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--out", type=Path, default=Path("_site"))
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    config = json.loads((args.source / "config.json").read_text())
    records = [json.loads(p.read_text()) for p in sorted((args.source / "records").glob("*/*.json"))]
    editions = [json.loads(p.read_text()) for p in sorted((args.source / "editions").glob("*/*/*.json"))]
    write_output(args.out, render(config, records, args.preview, editions))
    print(f"Rendered {len(records)} release(s) with renderer {VERSION}")


if __name__ == "__main__":
    main()
