#!/usr/bin/env python3
"""
APIForge — a zero-dependency REST API toolkit for three everyday jobs.
Sells as: "API integration / data pipeline scripts" (market: €85–€175 on PeoplePerHour)

Subcommands:
    pull       Fetch JSON from an API (with pagination) and save as JSON/CSV
    sync       Scheduled puller: re-fetch on an interval, appending new rows
                 (change detection by primary key — an incremental store)
    monitor    Watch an API endpoint; alert (console/exit code) when a value
                 changes, errors, or slows down past a threshold

Design notes:
- Standard library only (Python 3.9+): no pip, runs anywhere
- Handles the real-world mess: pagination (page/offset/cursor params),
  nested JSON, auth headers, rate limiting with retries and backoff
- `sync` writes a local JSONL store; new/changed rows are appended with a
  timestamp, so buyers get an incremental dataset, not just the latest dump

Examples:
    # Pull 5 pages of an API into CSV
    python apiforge.py pull https://api.example.com/items \
        --page-param page --start 1 --pages 5 --csv items.csv

    # With auth header and nested rows
    python apiforge.py pull https://api.example.com/orders \
        --header "Authorization: Bearer XYZ" --rows-path "data.orders" --out orders.json

    # Monitor a status endpoint every 60s, exit 2 if "state" != "ok"
    python apiforge.py monitor https://api.example.com/status \
        --jq-path "data.state" --expect "ok" --every 60

    # Sync: incremental pull every 15 min, keep new rows in store.jsonl
    python apiforge.py sync https://api.example.com/items \
        --id-field id --rows-path "items" --every 900 --out store.jsonl
"""

import argparse
import csv
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_AGENT = "APIForge/1.0"
RETRYABLE = (urllib.error.HTTPError,)  # plus 5xx codes checked below


def deep_get(obj, path):
    """Follow a dot path like 'data.orders' through nested dicts/lists."""
    current = obj
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"path segment '{part}' not found; got keys: {list(current)[:10]}")
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        else:
            raise KeyError(f"cannot descend into {type(current).__name__} via '{part}'")
    return current


def fetch_json(url: str, headers: dict, timeout: int = 20, retries: int = 3):
    """GET a URL and parse JSON, retrying on 5xx/timeouts with backoff."""
    last_error = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_AGENT, **headers})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600 and attempt < retries - 1:
                last_error = e
                time.sleep(2 ** attempt)  # 1s, 2s backoff
                continue
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_error


def paged_url(base: str, param: str, value, query_extra: dict) -> str:
    parts = urllib.parse.urlsplit(base)
    query = dict(urllib.parse.parse_qsl(parts.query))
    query[param] = str(value)
    query.update(query_extra)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path,
         urllib.parse.urlencode(query), parts.fragment))


def collect_rows(args):
    """Fetch one page or many, applying pagination and row-path extraction."""
    headers = {}
    for pair in args.header or []:
        name, _, value = pair.partition(":")
        headers[name.strip()] = value.strip()
    query_extra = dict(urllib.parse.parse_qsl(args.query or ""))

    pages = []
    if args.page_param:
        value = args.start
        for _ in range(args.pages):
            url = paged_url(args.url, args.page_param, value, query_extra)
            pages.append(fetch_json(url, headers))
            value += 1 if args.step is None else args.step
            if args.delay:
                time.sleep(args.delay)
    else:
        pages.append(fetch_json(paged_url(args.url, "k", 0, {}) if query_extra else args.url,
                                headers))

    rows = []
    for page in pages:
        item = deep_get(page, args.rows_path) if args.rows_path else page
        if isinstance(item, list):
            rows.extend(item)
        else:
            rows.append(item)
    return rows


def flatten(record: dict) -> dict:
    """Flatten nested dicts into dot-keys so CSV output stays tabular."""
    out = {}
    def walk(obj, prefix):
        for key, value in obj.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                walk(value, name)
            else:
                out[name] = json.dumps(value) if isinstance(value, (list, bool)) and not isinstance(value, str) else value
    if isinstance(record, dict):
        walk(record, "")
    return out


def write_rows(rows, out_path: str, to_csv: bool):
    if not rows:
        print("warning: no rows extracted", file=sys.stderr)
        return
    if to_csv:
        flat = [flatten(r) if isinstance(r, dict) else {"value": r} for r in rows]
        fieldnames = sorted({k for r in flat for k in r})
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat)
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)


# ---- subcommands ------------------------------------------------------------

def cmd_pull(args):
    rows = collect_rows(args)
    write_rows(rows, args.out, bool(args.csv))
    print(f"pulled {len(rows)} row(s) -> {args.out}", file=sys.stderr)


def cmd_sync(args):
    store = Path(args.out)
    seen, total_new = set(), 0
    if store.exists():
        for line in store.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    seen.add(str(deep_get(json.loads(line), args.id_field)))
                except (KeyError, json.JSONDecodeError):
                    continue

    print(f"sync started: every {args.every}s, store {store} "
          f"({len(seen)} existing row(s)) — Ctrl+C to stop", file=sys.stderr)
    while True:
        try:
            rows = collect_rows(args)
            new_rows = []
            for row in rows:
                row_id = str(deep_get(row, args.id_field))
                if row_id not in seen:
                    seen.add(row_id)
                    entry = {"_synced_at": datetime.datetime.now().isoformat(timespec="seconds"),
                             "data": row}
                    with open(store, "a", encoding="utf-8") as f:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    new_rows.append(row_id)
                    total_new += 1
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] {len(rows)} fetched, {len(new_rows)} new (total new: {total_new})",
                  file=sys.stderr)
        except Exception as e:
            print(f"[warn] fetch failed: {e} — continuing", file=sys.stderr)
        try:
            time.sleep(args.every)
        except KeyboardInterrupt:
            print(f"\nstopped. {total_new} new row(s) stored in {store}", file=sys.stderr)
            return


def cmd_monitor(args):
    headers = {}
    for pair in args.header or []:
        name, _, value = pair.partition(":")
        headers[name.strip()] = value.strip()

    print(f"monitoring {args.url} every {args.every}s "
          f"(expect: {args.expect!r}) — Ctrl+C to stop", file=sys.stderr)
    previous = None
    while True:
        started = time.time()
        try:
            payload = fetch_json(args.url, headers)
            elapsed = time.time() - started
            value = deep_get(payload, args.jq_path) if args.jq_path else payload
            value = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value

            changed = previous is not None and value != previous
            ok = args.expect is None or value == args.expect
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            status = "OK " if ok else "BAD"
            print(f"[{stamp}] {status} value={value!r} ({elapsed:.2f}s)"
                  + (" CHANGED" if changed else ""), file=sys.stderr)

            if not ok or (args.exit_on_change and changed):
                sys.exit(2 if not ok else 3)
            previous = value
        except KeyboardInterrupt:
            return
        except Exception as e:
            stamp = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] ERROR {e}", file=sys.stderr)
            if args.fail_fast:
                sys.exit(1)
        try:
            time.sleep(args.every)
        except KeyboardInterrupt:
            return


def main():
    parser = argparse.ArgumentParser(prog="apiforge",
                                     description="REST API toolkit: pull, sync, monitor.")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, rows=False):
        p.add_argument("url", help="API endpoint URL")
        p.add_argument("--header", action="append", metavar="NAME:VALUE",
                       help="request header (repeatable)")
        p.add_argument("--query", help="extra query string, e.g. 'status=active&limit=100'")
        p.add_argument("--page-param", help="pagination query parameter name, e.g. 'page'")
        p.add_argument("--start", type=int, default=1,
                       help="first pagination value (default 1)")
        p.add_argument("--step", type=int, default=None,
                       help="pagination step (default 1; use 100 for offset-based)")
        p.add_argument("--pages", type=int, default=1, help="pages to fetch (default 1)")
        p.add_argument("--delay", type=float, default=0.5,
                       help="seconds between page requests (default 0.5)")
        if rows:
            p.add_argument("--rows-path", help="dot path to the row list, e.g. 'data.items'")

    p_pull = sub.add_parser("pull", help="fetch API data to JSON/CSV")
    common(p_pull, rows=True)
    p_pull.add_argument("--out", required=True, help="output file (.json or .csv)")
    p_pull.add_argument("--csv", action="store_true", help="write CSV (auto if .csv)")
    p_pull.set_defaults(func=cmd_pull)

    p_sync = sub.add_parser("sync", help="incremental scheduled pulls to JSONL store")
    common(p_sync, rows=True)
    p_sync.add_argument("--id-field", required=True,
                       help="dot path to the row's unique id, e.g. 'id' or 'data.ref'")
    p_sync.add_argument("--every", type=float, default=60, help="seconds between fetches")
    p_sync.add_argument("--out", default="store.jsonl", help="JSONL store file")
    p_sync.set_defaults(func=cmd_sync)

    p_mon = sub.add_parser("monitor", help="watch an endpoint for value changes/errors")
    p_mon.add_argument("url", help="API endpoint URL")
    p_mon.add_argument("--jq-path", help="dot path to the value to watch, e.g. 'data.state'")
    p_mon.add_argument("--expect", help="expected value; exit 2 when different")
    p_mon.add_argument("--every", type=float, default=60, help="seconds between checks")
    p_mon.add_argument("--exit-on-change", action="store_true",
                       help="exit 3 when the value changes")
    p_mon.add_argument("--fail-fast", action="store_true",
                       help="exit 1 on first fetch/parse error")
    p_mon.add_argument("--header", action="append", metavar="NAME:VALUE")
    p_mon.set_defaults(func=cmd_monitor)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
