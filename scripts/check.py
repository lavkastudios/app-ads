#!/usr/bin/env python3
"""Guardrails before publishing. Any error -> exit 1 -> nothing is published, the live file stays as it is.

  python scripts/check.py            # validate dist/app-ads.txt and compare with live
  python scripts/check.py --force    # skip the size-change guard
  python scripts/check.py --offline  # no comparison with live
"""
from __future__ import annotations

import sys
import urllib.request

from appads import parse_line, parse_text
from common import ROOT, gh_output, gh_summary, load_config, sha256


def records(text: str) -> set[tuple[str, str, str]]:
    return {p.record.key for p in parse_text(text) if p.kind == "record"}


def validate(text: str, cfg: dict) -> list[str]:
    errors: list[str] = []
    size = len(text.encode("utf-8"))
    if size > cfg.get("max_bytes", 1_000_000):
        errors.append(f"file is {size} bytes, over the {cfg['max_bytes']} limit")
    if "<" in text or ">" in text:
        errors.append("file contains '<' or '>', looks like HTML")
    lines = text.splitlines()
    if not lines or lines[0].strip().lower() != f"ownerdomain={cfg['owner_domain']}":
        errors.append(f"first line must be ownerdomain={cfg['owner_domain']}")
    allowed = {v.lower() for v in cfg.get("allow_variables", [])}
    owner_count = 0
    keys: set = set()
    n = 0
    for i, line in enumerate(lines, 1):
        p = parse_line(line, lenient=False)
        if p.kind == "error":
            errors.append(f"line {i} is invalid ({p.error}): {line!r}")
        elif p.kind == "var":
            k, v = p.var
            if k == "ownerdomain":
                owner_count += 1
            elif f"{k}={v}".lower() not in allowed:
                errors.append(f"line {i}: variable {line!r} is not allowed in config.toml")
        elif p.kind == "record":
            n += 1
            if p.record.key in keys:
                errors.append(f"line {i}: duplicate {line!r}")
            keys.add(p.record.key)
            if p.record.line() != line.strip():
                errors.append(f"line {i} is not canonical: {line!r}")
    if owner_count != 1:
        errors.append(f"ownerdomain appears {owner_count} times (exactly 1 expected)")
    for acc in cfg.get("accounts", []):
        for p in parse_text((ROOT / acc["path"]).read_text(encoding="utf-8")):
            if p.record and p.record.key not in keys:
                errors.append(f"[{acc['path']}] required line missing: {p.record.line()}")
    if n < cfg.get("min_total_records", 1000):
        errors.append(f"only {n} records, suspiciously few")
    return errors


def fetch_live(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LavkaStudios-app-ads-updater/1.0",
                                                   "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8-sig", errors="replace")
    except Exception as e:  # noqa: BLE001
        print(f"WARN could not download the live file: {e}")
        return None


def main(argv: list[str]) -> int:
    cfg = load_config()
    text = (ROOT / cfg["output"]).read_text(encoding="utf-8")
    errors = validate(text, cfg)

    changed = True
    live = None if "--offline" in argv else fetch_live(cfg["live_url"])
    if live is not None:
        changed = sha256(live) != sha256(text)
        old, new = records(live), records(text)
        added, removed = sorted(new - old), sorted(old - new)
        md = [f"### app-ads.txt: {len(old)} → {len(new)} records (+{len(added)} / -{len(removed)})"]
        for title, items in (("Added", added), ("Removed", removed)):
            if items:
                md.append(f"<details><summary>{title}: {len(items)}</summary>\n\n```")
                md += [", ".join(k) for k in items[:300]]
                if len(items) > 300:
                    md.append(f"... and {len(items) - 300} more")
                md.append("```\n</details>")
        gh_summary("\n".join(md))
        if old and "--force" not in argv:
            if len(new) < len(old) * (1 - cfg["max_drop_ratio"]):
                errors.append(f"records went from {len(old)} to {len(new)} (drop over {cfg['max_drop_ratio']:.0%}). "
                              "If intended, run the workflow manually with force=true")
            if len(new) > len(old) * cfg["max_growth_ratio"]:
                errors.append(f"records went from {len(old)} to {len(new)} (growth over {cfg['max_growth_ratio']}x)")

    gh_output("changed", "true" if changed else "false")
    gh_output("sha256", sha256(text))
    if errors:
        gh_summary("### Checks failed, nothing will be published\n" + "\n".join(f"- {e}" for e in errors[:100]))
        return 1
    print(f"OK: checks passed, changed={changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
