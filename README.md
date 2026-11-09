# app-ads.txt for lavkastudios.com

Source of truth for https://lavkastudios.com/app-ads.txt. The file is built from the pieces in `sources/`,
checked, and served by a Cloudflare Worker that reads `dist/app-ads.txt` from this repository.

## Layout

```
sources/accounts/direct.txt       direct accounts (required lines)
sources/accounts/additional.txt   additional direct accounts (required lines)
sources/networks/*.txt            network seller lists
sources/additional/list.txt       additional seller list
config.toml                       source order, groups, limits
dist/app-ads.txt                  built file (do not edit by hand)
```

## Pipeline

1. `scripts/fetch.py` refreshes `kind = "url"` sources. A bad download keeps the previous version.
2. `scripts/build.py` normalises lines, fixes small typos, removes duplicates and writes `dist/app-ads.txt`.
3. `scripts/check.py` runs the guardrails below. If any fails, nothing is published.
4. The GitHub Action commits `dist/app-ads.txt`; the Worker picks it up (caches up to ~10 minutes).
5. `scripts/verify_live.py` checks that the live file matches the build.

The Action runs every Monday, on every push to `sources/`, `config.toml`, `scripts/` or `worker/`,
and manually (Actions -> app-ads.txt -> Run workflow).

## Guardrails

- every line is valid per the IAB spec, canonical, with no duplicates;
- the first line is `ownerdomain=lavkastudios.com`, no other variables unless listed in `allow_variables`;
- every line in `sources/accounts/*.txt` is present;
- no HTML, size under 1 MB, at least `min_total_records` records;
- compared with the live file, the record count does not drop by more than 25% or grow more than 2.5x
  (override with a manual run and `force = true`).

Downloaded sources must not be HTML, must have at least `min_records` records and must not shrink by more
than `max_drop_ratio`. Template lines with placeholders are dropped.

## Local run (Python 3.11+)

```
python scripts/build.py && python scripts/check.py
python -m unittest discover -s tests
```

`python scripts/extract_lines.py < email.txt` extracts seller lines from e-mail text where line breaks were lost.
