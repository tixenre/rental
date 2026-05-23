#!/usr/bin/env python3
"""
Export customers, orders, order lines and products from Booqable to CSV.

Uses the Boomerang (public) API, which is available on every plan including free.

Setup
-----
1. In Booqable: Settings -> Developers -> API keys -> create a key with
   read access to Customers, Orders, Lines and Products.
2. Export two env vars (or pass them as flags):
       export BOOQABLE_COMPANY=your-subdomain        # the part before .booqable.com
       export BOOQABLE_API_KEY=xxxxxxxxxxxxxxxxxxxx
3. Run:
       python3 tools/booqable_export.py
   Output goes to ./booqable_export/<timestamp>/{customers,orders,lines,products}.csv

Flags
-----
  --company SUBDOMAIN     overrides BOOQABLE_COMPANY
  --api-key KEY           overrides BOOQABLE_API_KEY
  --out DIR               output directory (default: ./booqable_export)
  --only customers,orders comma-separated list of resources to export
  --page-size N           items per page, max 100 (default: 100)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

RESOURCES = ("customers", "orders", "lines", "products")
API_BASE_TMPL = "https://{company}.booqable.com/api/boomerang/{resource}"
MAX_RETRIES = 8


def http_get(url: str, api_key: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/vnd.api+json",
            "User-Agent": "booqable-export/1.0",
        },
    )
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                # Honor Retry-After when provided; otherwise exponential backoff
                # starting at 30s for 429 (Booqable is strict) and 2s for 5xx.
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    wait = int(retry_after) if retry_after else None
                except ValueError:
                    wait = None
                if wait is None:
                    base = 30 if e.code == 429 else 2
                    wait = min(base * (2 ** (attempt - 1)), 300)
                print(f"  HTTP {e.code}, waiting {wait}s before retry {attempt}/{MAX_RETRIES}", file=sys.stderr)
                time.sleep(wait)
                continue
            raise SystemExit(f"HTTP {e.code} on {url}\n{body}")
        except urllib.error.URLError as e:
            if attempt < MAX_RETRIES:
                wait = min(2 * (2 ** (attempt - 1)), 60)
                time.sleep(wait)
                continue
            raise SystemExit(f"Network error on {url}: {e}")
    raise SystemExit(f"Exhausted retries on {url}")


def paginate(company: str, resource: str, api_key: str, page_size: int, delay: float = 0.0) -> Iterable[dict[str, Any]]:
    page = 1
    total = 0
    while True:
        params = urllib.parse.urlencode({
            "page[size]": page_size,
            "page[number]": page,
        }, safe="[]")
        url = API_BASE_TMPL.format(company=company, resource=resource) + "?" + params
        payload = http_get(url, api_key)
        items = payload.get("data", [])
        if not items:
            break
        for item in items:
            yield item
        total += len(items)
        print(f"  {resource}: fetched {total} so far", file=sys.stderr)
        meta = payload.get("meta", {}) or {}
        total_count = meta.get("total_count")
        if total_count is not None and total >= total_count:
            break
        if len(items) < page_size:
            break
        page += 1
        if delay > 0:
            time.sleep(delay)


def flatten(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten a JSON:API resource object into a flat dict suitable for CSV."""
    out: dict[str, Any] = {"id": item.get("id"), "type": item.get("type")}
    for k, v in (item.get("attributes") or {}).items():
        if isinstance(v, (dict, list)):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = v
    # Flatten relationships to their related ids only (full data is in its own export)
    for rel_name, rel in (item.get("relationships") or {}).items():
        data = rel.get("data") if isinstance(rel, dict) else None
        if isinstance(data, dict):
            out[f"rel_{rel_name}_id"] = data.get("id")
        elif isinstance(data, list):
            out[f"rel_{rel_name}_ids"] = ",".join(d.get("id", "") for d in data if isinstance(d, dict))
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    # Union of keys across all rows so no column is dropped if a record is missing it
    keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_resource(company: str, resource: str, api_key: str, page_size: int, out_dir: Path, delay: float = 0.0) -> int:
    print(f"Exporting {resource}...", file=sys.stderr)
    rows = [flatten(item) for item in paginate(company, resource, api_key, page_size, delay)]
    write_csv(out_dir / f"{resource}.csv", rows)
    print(f"  wrote {len(rows)} rows to {out_dir / (resource + '.csv')}", file=sys.stderr)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Booqable data to CSV via the Boomerang API.")
    parser.add_argument("--company", default=os.environ.get("BOOQABLE_COMPANY"))
    parser.add_argument("--api-key", default=os.environ.get("BOOQABLE_API_KEY"))
    parser.add_argument("--out", default="booqable_export", help="Output directory")
    parser.add_argument("--only", default=",".join(RESOURCES),
                        help=f"Comma-separated resources to export (any of: {','.join(RESOURCES)})")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Seconds to sleep between page requests to stay under rate limits (default: 0.5)")
    args = parser.parse_args()

    if not args.company:
        raise SystemExit("Missing --company or BOOQABLE_COMPANY (your subdomain, e.g. 'acme' for acme.booqable.com)")
    if not args.api_key:
        raise SystemExit("Missing --api-key or BOOQABLE_API_KEY")

    chosen = [r.strip() for r in args.only.split(",") if r.strip()]
    invalid = [r for r in chosen if r not in RESOURCES]
    if invalid:
        raise SystemExit(f"Unknown resources: {invalid}. Valid: {list(RESOURCES)}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    totals: dict[str, int] = {}
    for resource in chosen:
        totals[resource] = export_resource(args.company, resource, args.api_key, args.page_size, out_dir, args.delay)

    print("\nDone. Output:", out_dir, file=sys.stderr)
    for r, n in totals.items():
        print(f"  {r}: {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
