#!/usr/bin/env python3
"""Extract app-ads.txt lines from e-mail text (where line breaks were lost).

  python scripts/extract_lines.py < email.txt >> sources/networks/90-verve-email-lines.txt
"""
import sys

from appads import extract_records

for r in extract_records(sys.stdin.read()):
    print(r.line())
