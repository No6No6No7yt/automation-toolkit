#!/usr/bin/env python3
r"""
CSVKit — a zero-dependency CSV cleaning & merging toolkit.
Sells as: "data cleansing / merge spreadsheets / dedupe data" — the
highest-volume data category on PeoplePerHour (€15–€60 per job, huge demand)

Subcommands:
    merge       Combine multiple CSVs; aligns columns, optional dedupe
    dedupe      Remove duplicate rows (by full row or by key columns)
    clean       Standardize: trim whitespace, unify empties, drop bad rows
    pivot       Reshape long->wide (group by key column, spread value column)
    compare     Diff two CSVs row-by-row, report new/removed/changed

Design notes:
- Standard library only (Python 3.9+); no pandas, no Excel license issues
- Excel-friendly: reads UTF-8-sig (Excel's BOM), writes UTF-8-sig
- `clean` never deletes data rows by default — only obvious garbage
  (fully empty rows); other fixes are in-place value fixes
- All destructive ops print what they did

Examples:
    python csvkit.py merge jan.csv feb.csv mar.csv --out q1.csv
    python csvkit.py merge *.csv --out all.csv --dedupe
    python csvkit.py dedupe customers.csv --key email --out clean.csv
    python csvkit.py clean messy.csv --out clean.csv
    python csvkit.py pivot long.csv --key date --spread region --value sales --out wide.csv
    python csvkit.py compare old.csv new.csv --id email --out changes.csv
"""

import argparse
import csv
import glob
import sys
from collections import OrderedDict
from pathlib import Path


def read_csv(path: str):
    """Read a CSV, return (fieldnames, rows-as-dicts). Handles Excel BOM."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader if any((v or "").strip() for v in r.values())]
        fieldnames = reader.fieldnames or []
    return [fn.strip() for fn in fieldnames], rows


def write_csv(path: str, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def expand_globs(paths):
    out = []
    for pattern in paths:
        matches = sorted(glob.glob(pattern))
        out.extend(matches if matches else [pattern])
    return out


# ---- subcommands ------------------------------------------------------------

def cmd_merge(args):
    files = expand_globs(args.files)
    if len(files) < 2:
        sys.exit("error: merge needs at least 2 files")
    columns = OrderedDict()  # ordered union of all fieldnames
    all_rows = []
    per_file_counts = []
    for path in files:
        if not Path(path).is_file():
            sys.exit(f"error: {path} not found")
        fieldnames, rows = read_csv(path)
        for fn in fieldnames:
            columns[fn] = True
        all_rows.extend(rows)
        per_file_counts.append((path, len(rows)))

    merged = list(all_rows)
    removed = 0
    if args.dedupe:
        seen, deduped = set(), []
        for row in merged:
            key = tuple(row.get(c, "") for c in columns)
            if key not in seen:
                seen.add(key)
                deduped.append(row)
            else:
                removed += 1
        merged = deduped

    write_csv(args.out, list(columns), merged)
    for path, count in per_file_counts:
        print(f"  + {path}: {count} row(s)")
    print(f"merged: {len(all_rows)} row(s) in, {len(merged)} out"
          + (f" ({removed} duplicate(s) removed)" if args.dedupe else "")
          + f" -> {args.out}")


def cmd_dedupe(args):
    fieldnames, rows = read_csv(args.file)
    if not rows:
        sys.exit("error: no data rows")
    keys = args.key.split(",") if args.key else None
    seen, kept, removed = set(), [], 0
    for row in rows:
        if keys:
            key = tuple((row.get(k, "") or "").strip().lower() for k in keys)
        else:
            key = tuple(row.get(fn, "") for fn in fieldnames)
        if key in seen:
            removed += 1
        else:
            seen.add(key)
            kept.append(row)
    write_csv(args.out or args.file, fieldnames, kept)
    print(f"dedupe: {len(rows)} -> {len(kept)} row(s) ({removed} removed)"
          + (f" by key {keys}" if keys else " by full row"))
    if not args.out:
        print(f"note: overwrote {args.file} in place")


def cmd_clean(args):
    fieldnames, rows = read_csv(args.file)
    fixes = {"trimmed": 0, "blank_normalized": 0, "case_fixed": 0,
             "whitespace_collapsed": 0, "dropped_rows": 0}
    cleaned = []
    for row in rows:
        keep = True
        for fn in fieldnames:
            value = row.get(fn) or ""
            if value != value.strip():
                fixes["trimmed"] += 1
            value = value.strip()
            collapsed = " ".join(value.split())
            if collapsed != value:
                fixes["whitespace_collapsed"] += 1
            if value in ("N/A", "n/a", "NULL", "null", "-", "None", "none"):
                fixes["blank_normalized"] += 1
                value = ""
            if args.emails and ("@" in fn.lower() or "@" in value):
                value = value.strip().rstrip(".").replace(" ", "")
                fixes["case_fixed"] += 1
                value = value.lower()
            row[fn] = value
            if args.drop_rows_missing:
                missing = args.drop_rows_missing.split(",")
                if all(not row.get(m, "").strip() for m in missing):
                    keep = False
        if keep:
            cleaned.append(row)
        else:
            fixes["dropped_rows"] += 1

    write_csv(args.out or args.file, fieldnames, cleaned)
    print(f"clean: {len(rows)} row(s) -> {len(cleaned)} ({fixes['dropped_rows']} dropped)")
    for label, count in fixes.items():
        if count and label != "dropped_rows":
            print(f"  {label}: {count} value(s) fixed")
    if not args.out:
        print(f"note: overwrote {args.file} in place")


def cmd_pivot(args):
    fieldnames, rows = read_csv(args.file)
    for required in (args.key, args.spread, args.value):
        if required not in fieldnames:
            sys.exit(f"error: column '{required}' not in {fieldnames}")

    wide = {}          # key -> {spread_value: aggregate}
    spread_values = OrderedDict()
    for row in rows:
        key = (row.get(args.key, "") or "").strip()
        spread = (row.get(args.spread, "") or "").strip() or "(blank)"
        raw = (row.get(args.value, "") or "").strip()
        try:
            number = float(raw.replace(",", ""))
        except ValueError:
            sys.exit(f"error: value '{raw!r}' in row for key '{key}' is not numeric")
        wide.setdefault(key, {})
        wide[key][spread] = wide[key].get(spread, 0) + number  # sum duplicates
        spread_values[spread] = True

    out_fields = [args.key] + list(spread_values)
    out_rows = []
    for key, values in wide.items():
        out_rows.append({args.key: key,
                         **{s: values.get(s, "") for s in spread_values}})
    write_csv(args.out, out_fields, out_rows)
    print(f"pivot: {len(rows)} long row(s) -> {len(out_rows)} wide row(s), "
          f"{len(spread_values)} '{args.spread}' column(s) -> {args.out}")


def cmd_compare(args):
    fields_old, old_rows = read_csv(args.old)
    fields_new, new_rows = read_csv(args.new)
    id_field = args.id or (set(fields_old) & set(fields_new))
    if isinstance(id_field, set):
        if not id_field:
            sys.exit("error: no shared columns; use --id COLUMN")
        id_field = sorted(id_field)[0]

    old_by_id = {(r.get(id_field, "") or "").strip().lower(): r for r in old_rows}
    new_by_id = {(r.get(id_field, "") or "").strip().lower(): r for r in new_rows}

    added = [new_by_id[k] for k in new_by_id if k not in old_by_id]
    removed = [old_by_id[k] for k in old_by_id if k not in new_by_id]
    changed = []
    for key in new_by_id:
        if key in old_by_id:
            o, n = old_by_id[key], new_by_id[key]
            diffs = {fn: (o.get(fn, ""), n.get(fn, ""))
                     for fn in fields_new
                     if fn in fields_old and (o.get(fn, "") or "") != (n.get(fn, "") or "")}
            if diffs:
                changed.append({"_id": n.get(id_field, ""), "_changes": len(diffs), **n})

    print(f"compare by '{id_field}': {len(added)} added, {len(removed)} removed, "
          f"{len(changed)} changed")
    if args.out:
        out_fields = ["_status", id_field] + [f for f in fields_new if f != id_field]
        out_rows = [dict(r, _status="added") for r in added]
        out_rows += [dict(r, _status="changed") for r in changed]
        out_rows += [dict(r, _status="removed") for r in removed]
        write_csv(args.out, out_fields, out_rows)
        print(f"changes written -> {args.out}")


def main():
    parser = argparse.ArgumentParser(prog="csvkit",
                                     description="CSV merge/clean/dedupe/pivot/compare toolkit.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("merge", help="combine multiple CSVs (globs ok)")
    p.add_argument("files", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--dedupe", action="store_true", help="drop identical rows")
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("dedupe", help="remove duplicate rows")
    p.add_argument("file")
    p.add_argument("--key", help="comma-separated key columns (default: full row)")
    p.add_argument("--out", help="output file (default: overwrite input)")
    p.set_defaults(func=cmd_dedupe)

    p = sub.add_parser("clean", help="standardize values")
    p.add_argument("file")
    p.add_argument("--emails", action="store_true", help="normalize @-containing values")
    p.add_argument("--drop-rows-missing", metavar="COLS",
                   help="drop rows where ALL of these columns are empty")
    p.add_argument("--out", help="output file (default: overwrite input)")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("pivot", help="long -> wide reshape (sums values)")
    p.add_argument("file")
    p.add_argument("--key", required=True, help="column to group by")
    p.add_argument("--spread", required=True, help="column whose values become columns")
    p.add_argument("--value", required=True, help="numeric column to sum")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_pivot)

    p = sub.add_parser("compare", help="diff two CSVs by an id column")
    p.add_argument("old")
    p.add_argument("new")
    p.add_argument("--id", help="id column (default: first shared column)")
    p.add_argument("--out", help="write added/removed/changed rows to CSV")
    p.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
