#!/usr/bin/env python3
"""After publishing: wait until https://lavkastudios.com/app-ads.txt serves exactly the built file."""
import sys
import time

from check import fetch_live
from common import ROOT, load_config, sha256

cfg = load_config()
want = sha256((ROOT / cfg["output"]).read_text(encoding="utf-8"))
for attempt in range(42):
    live = fetch_live(cfg["live_url"] + f"?v={int(time.time())}")
    if live is not None and sha256(live) == want:
        print("OK: live file matches the build")
        sys.exit(0)
    time.sleep(15)
print("ERROR: live file did not match the build within 10 minutes")
sys.exit(1)
