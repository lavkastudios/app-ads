#!/usr/bin/env python3
"""Refresh kind="url" sources. A bad response keeps the previous version of the file (with a warning)."""
from __future__ import annotations

import datetime as dt
import sys
import urllib.request

from appads import parse_text
from common import ROOT, gh_summary, load_config

UA = "LavkaStudios-app-ads-updater/1.0 (+https://lavkastudios.com)"


def url_for(src: dict) -> str:
    if src["kind"] == "gdoc":
        return f"https://docs.google.com/document/d/{src['doc_id']}/export?format=txt"
    return src["url"]


def download(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/plain,*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        status = getattr(r, "status", None) or 200  # file:// URLs (tests) have no status
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        raw = r.read(5_000_000)
        ctype = r.headers.get("content-type", "")
    text = raw.decode("utf-8-sig", errors="replace")
    if "html" in ctype.lower() or text.lstrip().lower().startswith(("<!doctype", "<html")):
        raise RuntimeError(f"got HTML instead of text ({ctype})")
    return text


def refresh(src: dict) -> str:
    url = url_for(src)
    text = download(url)
    parsed = parse_text(text)
    strip = {d.lower() for d in src.get("strip_direct_for", [])}
    recs, bad = [], 0
    seen = set()
    out_lines = []
    for p in parsed:
        if p.kind == "record":
            r = p.record
            if r.key in seen:
                continue
            seen.add(r.key)
            if r.rel == "DIRECT" and r.domain in strip:
                continue  # template DIRECT line from the network; our DIRECT line is kept in sources/accounts
            recs.append(r)
            out_lines.append(r.line())
        elif p.kind == "error":
            bad += 1
    total = len(recs) + bad
    min_records = src.get("min_records", 1)
    if len(recs) < min_records:
        raise RuntimeError(f"only {len(recs)} valid records (minimum {min_records})")
    if total and bad / total > src.get("max_bad_ratio", 0.2):
        raise RuntimeError(f"{bad} of {total} lines do not parse")
    path = ROOT / src["path"]
    if path.exists():
        prev = sum(1 for p in parse_text(path.read_text(encoding="utf-8")) if p.kind == "record")
        if prev and len(recs) < prev * (1 - src.get("max_drop_ratio", 0.5)):
            raise RuntimeError(f"records went from {prev} to {len(recs)}, suspicious drop")
    header = [f"# {src.get('title', src['id'])}", f"# source: {url}",
              f"# fetched: {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC"]
    body = [l for l in out_lines if not l.startswith(("# source:", "# fetched:"))]
    new = "\n".join(header + body) + "\n"
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    strip_ts = lambda s: "\n".join(l for l in s.splitlines() if not l.startswith("# fetched:"))
    if strip_ts(old) == strip_ts(new):
        return f"unchanged ({len(recs)})"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8")
    return f"updated ({len(recs)} records)"


def main() -> int:
    cfg = load_config()
    rows, failed = [], 0
    for src in cfg["source"]:
        if src["kind"] not in ("url", "gdoc"):
            continue
        try:
            status = refresh(src)
        except Exception as e:  # noqa: BLE001 - any error keeps the previous version
            failed += 1
            status = f"error, previous version kept: {e}"
        rows.append(f"| {src['id']} | {status} |")
    gh_summary("### Sources\n| source | status |\n|---|---|\n" + "\n".join(rows))
    # A failing source does not break the build: its previous version is used.
    return 0


if __name__ == "__main__":
    sys.exit(main())
