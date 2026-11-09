"""Parsing, normalisation and validation helpers for app-ads.txt (IAB ads.txt 1.1)."""
from __future__ import annotations

import re
from dataclasses import dataclass

RELATIONSHIPS = {"DIRECT", "RESELLER"}
VARIABLES = {"contact", "subdomain", "ownerdomain", "managerdomain", "inventorypartnerdomain"}
# Common typos seen in partner files -> canonical relationship.
REL_FIXES = {"RESELLE": "RESELLER", "RESELER": "RESELLER", "RESSELLER": "RESELLER",
             "RESELLLER": "RESELLER", "DIRCET": "DIRECT", "DIREC": "DIRECT"}
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}$")
CERT_RE = re.compile(r"^[A-Za-z0-9]{6,32}$")
ACCOUNT_RE = re.compile(r"^[A-Za-z0-9._:@+/=-]{1,128}$")
PLACEHOLDER_RE = re.compile(r"(to be added|your|placeholder|xxxx|publisher.?id|account.?id|\[|\]|<|>|\{|\})", re.I)


@dataclass(frozen=True)
class Record:
    domain: str
    account: str
    rel: str
    cert: str = ""

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.domain, self.account, self.rel)

    def line(self) -> str:
        parts = [self.domain, self.account, self.rel] + ([self.cert] if self.cert else [])
        return ", ".join(parts)


@dataclass
class Parsed:
    kind: str            # blank | comment | var | record | error
    raw: str
    record: Record | None = None
    var: tuple[str, str] | None = None
    error: str = ""


def _clean(raw: str) -> str:
    s = raw.replace("﻿", "").replace(" ", " ").replace("​", "")
    s = s.replace("\\_", "_").replace("\\#", "#")      # markdown escapes from Google Docs
    return s.strip().strip('"').strip()


def split_physical(text: str) -> list[str]:
    """Split text into logical lines, undoing CSV-style '","' joins."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    for line in text.split("\n"):
        out.extend(line.split('","'))
    return out


def parse_line(raw: str, lenient: bool = True) -> Parsed:
    s = _clean(raw)
    if not s:
        return Parsed("blank", raw)
    if s.startswith("#"):
        return Parsed("comment", raw)
    s = s.split("#", 1)[0].strip()
    if "=" in s and "," not in s:
        k, v = s.split("=", 1)
        k = k.strip().lower()
        if k in VARIABLES and v.strip():
            return Parsed("var", raw, var=(k, v.strip()))
        return Parsed("error", raw, error="unknown variable")
    if lenient and s.count(",") == 2:
        # 'domain, id, RESELLER 0bfd66d529a55807' -> missing comma before cert
        a, b, c = [p.strip() for p in s.split(",")]
        bits = c.split()
        if len(bits) == 2 and bits[0].upper() in RELATIONSHIPS | set(REL_FIXES):
            s = ", ".join([a, b, bits[0], bits[1]])
    parts = [p.strip() for p in s.split(",")]
    while parts and parts[-1] == "":
        parts.pop()
    if len(parts) < 3:
        return Parsed("error", raw, error="fewer than 3 fields")
    domain, account, rel = parts[0].lower(), parts[1], parts[2].upper()
    cert = parts[3] if len(parts) > 3 else ""
    if lenient:
        rel = REL_FIXES.get(rel, rel)
        rel = rel.split()[0] if rel.split() and rel.split()[0] in RELATIONSHIPS else rel
    if not DOMAIN_RE.match(domain):
        return Parsed("error", raw, error=f"bad domain '{domain}'")
    if rel not in RELATIONSHIPS:
        return Parsed("error", raw, error=f"bad relationship '{parts[2]}'")
    if not ACCOUNT_RE.match(account) or PLACEHOLDER_RE.search(account):
        return Parsed("error", raw, error=f"bad/placeholder account '{account}'")
    if cert and not CERT_RE.match(cert):
        if lenient:
            cert = ""
        else:
            return Parsed("error", raw, error=f"bad certification id '{cert}'")
    return Parsed("record", raw, record=Record(domain, account, rel, cert.lower()))


def parse_text(text: str, lenient: bool = True) -> list[Parsed]:
    return [parse_line(l, lenient) for l in split_physical(text)]


# Glued text from e-mails: "…, RESELLERgreyalpha.agency, id, RESELLER, 819580c2afa8a3aavideoshakers.tv, …"
_GLUED_RE = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,})\s*,\s*([^,\s]+)\s*,\s*(DIRECT|RESELLER|RESELER|RESELLE)"
    r"(?:\s*,\s*([0-9a-f]{16}))?",
    re.I,
)


def extract_records(text: str) -> list[Record]:
    """Pull records out of free text (e-mails) where line breaks were lost."""
    flat = re.sub(r"\s+", " ", text)
    out: list[Record] = []
    for m in _GLUED_RE.finditer(flat):
        p = parse_line(", ".join(x for x in m.groups() if x))
        if p.record:
            out.append(p.record)
    return out
