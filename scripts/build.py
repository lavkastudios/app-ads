#!/usr/bin/env python3
"""Build dist/app-ads.txt from the sources listed in config.toml (order, normalisation, de-duplication)."""
from __future__ import annotations

import sys

from appads import parse_text
from common import ROOT, load_config


BAR = "# " + "=" * 70


def _block(title: str) -> list[str]:
    return ["", BAR, f"# {title}", BAR]


def build(cfg: dict) -> tuple[str, list[str]]:
    """ownerdomain -> [[accounts]] blocks -> reseller groups (sorted, de-duplicated)."""
    warnings: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    lines = [f"ownerdomain={cfg['owner_domain']}"]
    lines += list(cfg.get("allow_variables", []))

    for acc in cfg.get("accounts", []):
        path = ROOT / acc["path"]
        lines += _block(acc["title"])
        for p in parse_text(path.read_text(encoding="utf-8")):
            if p.kind == "comment":
                lines.append(p.raw.strip())
            elif p.kind == "record":
                if p.record.key in seen:
                    warnings.append(f"[{acc['path']}] duplicate account line {p.record.line()!r}")
                    continue
                seen.add(p.record.key)
                lines.append(p.record.line())
            elif p.kind in ("error", "var"):
                raise SystemExit(f"{acc['path']}: invalid line {p.raw.strip()!r} ({p.error or 'variable'})")

    groups = cfg.get("reseller_groups") or [{"id": "main", "title": "Resellers"}]
    known = {g["id"] for g in groups}
    for src in cfg["source"]:
        if src.get("group", "main") not in known:
            raise SystemExit(f"[{src['id']}] unknown group {src.get('group')!r}")
    for g in groups:
        resellers: dict[tuple[str, str, str], str] = {}
        for src in cfg["source"]:
            if src.get("group", "main") != g["id"]:
                continue
            path = ROOT / src["path"]
            if not path.exists():
                warnings.append(f"[{src['id']}] file {src['path']} not found, skipped")
                continue
            for p in parse_text(path.read_text(encoding="utf-8")):
                if p.kind == "record":
                    if p.record.key not in seen and p.record.key not in resellers:
                        resellers[p.record.key] = p.record.line()
                elif p.kind == "error":
                    warnings.append(f"[{src['id']}] skipped line {p.raw.strip()!r}: {p.error}")
                elif p.kind == "var":
                    warnings.append(f"[{src['id']}] variable {p.raw.strip()!r} dropped (only allow_variables are kept)")
        seen.update(resellers)
        lines += _block(g["title"])
        lines += [resellers[k] for k in sorted(resellers, key=lambda k: (k[0], k[1].lower(), k[2]))]
    return "\n".join(lines) + "\n", warnings


def main() -> int:
    cfg = load_config()
    text, warnings = build(cfg)
    out = ROOT / cfg["output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    for w in warnings:
        print("WARN", w)
    n = sum(1 for l in text.splitlines() if l and not l.startswith("#") and "," in l)
    print(f"built {out.relative_to(ROOT)}: {n} records, {len(text.encode())} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
