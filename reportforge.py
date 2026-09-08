#!/usr/bin/env python3
"""
ReportForge — a zero-dependency CSV -> styled report generator.
Sells as: "data research / insights report with charts" (€30–€310 on PeoplePerHour)

What it does:
    Reads any CSV, computes per-column statistics (numeric: min/max/mean/
    quartiles; categorical: top values with counts), renders clean bar
    charts inline (pure SVG, no JS libraries), and emits a single
    self-contained HTML report — openable in any browser, printable to PDF.

Why HTML-not-PDF: a single self-contained file with zero dependencies that
prints to PDF from any browser. The buyer gets a portable deliverable and
the seller avoids PDF library licensing/dependency mess.

Usage:
    python reportforge.py sales.csv --title "Q3 Sales Report" --out report.html
    python reportforge.py survey.csv --bars 8 --columns age,satisfaction
    python reportforge.py logs.csv --group-by country --out summary.html

Selling model: buyer sends a CSV/spreadsheet (Excel exports to CSV in one
click), gets back a branded insight report. Upsells: custom grouping,
per-segment sections, scheduled regeneration via apiforge sync.
"""

import argparse
import csv
import datetime
import html
import io
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

PALETTE = ["#4f6df5", "#22c55e", "#e59313", "#e2495b", "#8b5cf6",
           "#06b6d4", "#f472b6", "#84cc16"]


# ---------- parsing & stats -------------------------------------------------

def coerce(value: str):
    """Try int, then float, else keep string."""
    value = value.strip()
    if not value:
        return ""
    try:
        number = float(value)
        return int(number) if number == int(number) and "." not in value and "e" not in value.lower() else number
    except ValueError:
        return value


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_csv(path: str):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [{k: coerce(v) for k, v in row.items() if k}
                for row in reader if any(v.strip() for v in row.values() if v)]
    if not rows:
        sys.exit("error: CSV contains no data rows")
    return rows


def numeric_column(rows, key):
    return [r[key] for r in rows if is_number(r.get(key))]


def column_stats(rows, key):
    """Stats dict for one column; None if it can't be summarized."""
    numbers = numeric_column(rows, key)
    if len(numbers) >= 3:
        sorted_n = sorted(numbers)
        q1 = sorted_n[len(sorted_n) // 4]
        q3 = sorted_n[3 * len(sorted_n) // 4]
        return {"kind": "numeric", "key": key,
                "count": len(numbers), "sum": sum(numbers),
                "mean": statistics.fmean(numbers),
                "min": min(numbers), "max": max(numbers),
                "q1": q1, "median": statistics.median(numbers), "q3": q3}
    values = [r[key] for r in rows if r.get(key) not in ("", None)]
    if len(values) >= 3:
        counts = Counter(str(v) for v in values)
        return {"kind": "categorical", "key": key,
                "count": len(values),
                "unique": len(counts),
                "top": counts.most_common(5)}
    return None


def group_summary(rows, group_key):
    """Group rows by a categorical column; numeric stats per group."""
    groups = {}
    for row in rows:
        groups.setdefault(str(row.get(group_key, "∅")), []).append(row)
    out = []
    for name, group in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        entry = {"group": name, "rows": len(group), "stats": []}
        numeric_keys = [k for k in group[0]
                        if sum(1 for r in group[:5] if is_number(r.get(k))) >= 3]
        for key in numeric_keys:
            numbers = numeric_column(group, key)
            entry["stats"].append({
                "key": key, "mean": statistics.fmean(numbers),
                "sum": sum(numbers), "min": min(numbers), "max": max(numbers)})
        out.append(entry)
    return out


# ---------- SVG charts (no dependencies, inline) ---------------------------

def fmt_number(n: float) -> str:
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 10_000:
        return f"{n / 1_000:.0f}k"
    if isinstance(n, float) and n != int(n):
        return f"{n:,.1f}"
    return f"{int(n):,}"


def bar_chart_svg(label_value_pairs, width=640, bar_height=26, title=""):
    """Horizontal bar chart as inline SVG. Values must be numeric."""
    if not label_value_pairs:
        return "<p class='muted'>(no data)</p>"
    max_value = max(v for _, v in label_value_pairs) or 1
    label_w = min(220, max(len(l) for l, _ in label_value_pairs) * 7 + 12)
    chart_w = width - label_w - 90
    total_h = len(label_value_pairs) * (bar_height + 8) + 40 + (14 if title else 0)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_h}" '
             f'viewBox="0 0 {width} {total_h}" role="img">']
    if title:
        parts.append(f'<text x="0" y="16" class="chart-title">{html.escape(title)}</text>')
    y0 = 30 + (14 if title else 0)
    for i, (label, value) in enumerate(label_value_pairs):
        y = y0 + i * (bar_height + 8)
        color = PALETTE[i % len(PALETTE)]
        bar_w = max(2, (value / max_value) * chart_w)
        parts.append(
            f'<text x="{label_w - 6}" y="{y + bar_height * 0.7}" text-anchor="end" '
            f'class="chart-label">{html.escape(str(label)[:32])}</text>'
            f'<rect x="{label_w}" y="{y}" width="{bar_w:.1f}" height="{bar_height}" rx="5" '
            f'fill="{color}"></rect>'
            f'<text x="{label_w + bar_w + 8:.1f}" y="{y + bar_height * 0.7}" '
            f'class="chart-value">{fmt_number(value)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def histogram_svg(numbers, key, bins=20, width=640, height=180):
    """Distribution histogram for a numeric column."""
    if len(numbers) < 4:
        return "<p class='muted'>(not enough numeric values)</p>"
    lo, hi = min(numbers), max(numbers)
    if lo == hi:
        return f"<p class='muted'>(all values equal {fmt_number(lo)})</p>"
    width_bin = (hi - lo) / bins
    counts = [0] * bins
    for n in numbers:
        idx = min(bins - 1, int((n - lo) / width_bin))
        counts[idx] += 1
    max_count = max(counts)
    chart_w = width - 70
    bar_w = chart_w / bins
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height + 34}" '
             f'viewBox="0 0 {width} {height + 34}" role="img">']
    parts.append(f'<text x="0" y="14" class="chart-title">'
                 f'{html.escape(key)} — distribution</text>')
    for i, count in enumerate(counts):
        bar_h = (count / max_count) * (height - 30)
        if bar_h < 1:
            continue
        x = 50 + i * bar_w
        y = height - bar_h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(1, bar_w - 1):.1f}" '
                     f'height="{bar_h:.1f}" fill="{PALETTE[0]}"></rect>')
    parts.append(f'<text x="50" y="{height + 14}" class="chart-axis">{fmt_number(lo)}</text>')
    parts.append(f'<text x="{width - 20}" y="{height + 14}" class="chart-axis" text-anchor="end">'
                 f'{fmt_number(hi)}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------- HTML rendering ---------------------------------------------------

CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 0;
       background: #f4f5f8; color: #1d2433; }
.page { max-width: 780px; margin: 24px auto; background: #fff; padding: 40px 48px;
        border-radius: 12px; box-shadow: 0 2px 16px rgba(20,30,60,.08); }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 17px; margin: 32px 0 12px; color: #4f6df5;
     text-transform: uppercase; letter-spacing: .06em; }
.meta { color: #7a8299; font-size: 13px; margin-bottom: 28px; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
th { text-align: left; color: #7a8299; font-weight: 600; padding: 8px 10px;
     border-bottom: 2px solid #e6e9f2; }
td { padding: 7px 10px; border-bottom: 1px solid #eef0f6; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.kpis { display: flex; flex-wrap: wrap; gap: 12px; margin: 18px 0 6px; }
.kpi { flex: 1 1 150px; background: #f4f6ff; border-radius: 10px; padding: 14px 16px; }
.kpi .label { font-size: 11.5px; color: #7a8299; text-transform: uppercase;
              letter-spacing: .05em; }
.kpi .value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.chart-label { font-size: 12px; fill: #3a4358; }
.chart-value { font-size: 12px; fill: #1d2433; font-weight: 600; }
.chart-title { font-size: 13px; fill: #1d2433; font-weight: 600; }
.chart-axis { font-size: 11px; fill: #7a8299; }
.muted { color: #9aa1b5; }
footer { margin-top: 40px; font-size: 11.5px; color: #9aa1b5; }
@media print { body { background: #fff; } .page { box-shadow: none; margin: 0;
             max-width: none; } }
"""


def kpi_card(label, value):
    return (f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
            f'<div class="value">{html.escape(value)}</div></div>')


def render_report(title, csv_path, rows, columns, group_by, top_bars):
    all_keys = list(rows[0].keys())
    keys = columns or all_keys

    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><div class='page'>",
        f"<h1>{html.escape(title)}</h1>",
        f"<div class='meta'>Source: {html.escape(csv_path)} — {len(rows):,} rows, "
        f"{len(all_keys)} columns — generated {datetime.datetime.now():%Y-%m-%d %H:%M}</div>",
    ]

    # KPI strip
    parts.append('<div class="kpis">')
    parts.append(kpi_card("Rows", f"{len(rows):,}"))
    for key in keys:
        numbers = numeric_column(rows, key)
        if len(numbers) >= 3:
            parts.append(kpi_card(f"{key} · total", fmt_number(sum(numbers))))
            parts.append(kpi_card(f"{key} · mean", fmt_number(statistics.fmean(numbers))))
    parts.append("</div>")

    # Per-column sections
    for key in keys:
        stats = column_stats(rows, key)
        if not stats:
            continue
        parts.append(f"<h2>{html.escape(key)}</h2>")
        if stats["kind"] == "numeric":
            parts.append("<table><tbody>")
            for label, value in [("count", f"{stats['count']:,}"),
                                 ("sum", fmt_number(stats["sum"])),
                                 ("mean", fmt_number(stats["mean"])),
                                 ("min", fmt_number(stats["min"])),
                                 ("Q1 / median / Q3",
                                  f"{fmt_number(stats['q1'])} / {fmt_number(stats['median'])} / {fmt_number(stats['q3'])}"),
                                 ("max", fmt_number(stats["max"]))]:
                parts.append(f"<tr><td>{html.escape(label)}</td>"
                             f"<td class='num'>{value}</td></tr>")
            parts.append("</tbody></table>")
            numbers = numeric_column(rows, key)
            parts.append(histogram_svg(numbers, key))
        else:
            top = stats["top"][:top_bars]
            chart = bar_chart_svg(
                [(label, count) for label, count in top],
                title=f"{key} — top {len(top)} of {stats['unique']} values")
            parts.append(chart)
            parts.append(f"<p class='muted'>{stats['unique']:,} distinct values, "
                         f"{stats['count']:,} non-empty</p>")

    # Group section
    if group_by:
        parts.append(f"<h2>Segments — by {html.escape(group_by)}</h2>")
        for entry in group_summary(rows, group_by)[:top_bars]:
            parts.append(f"<h3 style='margin:18px 0 6px'>{html.escape(entry['group'])} "
                         f"<span class='muted'>({entry['rows']:,} rows)</span></h3>")
            if entry["stats"]:
                parts.append("<table><thead><tr><th>metric</th><th class='num'>mean</th>"
                             "<th class='num'>total</th><th class='num'>min</th>"
                             "<th class='num'>max</th></tr></thead><tbody>")
                for s in entry["stats"]:
                    parts.append(f"<tr><td>{html.escape(s['key'])}</td>"
                                 f"<td class='num'>{fmt_number(s['mean'])}</td>"
                                 f"<td class='num'>{fmt_number(s['sum'])}</td>"
                                 f"<td class='num'>{fmt_number(s['min'])}</td>"
                                 f"<td class='num'>{fmt_number(s['max'])}</td></tr>")
                parts.append("</tbody></table>")

    parts.append("<footer>Generated with ReportForge — self-contained HTML, "
                 "print to PDF from any browser (Ctrl+P).</footer>")
    parts.append("</div></body></html>")
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(description="CSV -> styled insight report (HTML).")
    parser.add_argument("csv", help="input CSV file")
    parser.add_argument("--title", default="Data Report")
    parser.add_argument("--out", default="report.html")
    parser.add_argument("--columns", help="comma-separated columns to analyze (default: all)")
    parser.add_argument("--group-by", help="categorical column to segment by")
    parser.add_argument("--bars", type=int, default=8, help="bars/values per chart (default 8)")
    args = parser.parse_args()

    rows = load_csv(args.csv)
    columns = [c.strip() for c in args.columns.split(",")] if args.columns else None
    report = render_report(args.title, args.csv, rows, columns, args.group_by, args.bars)
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"report written: {args.out} "
          f"({len(rows):,} rows) — open in a browser, Ctrl+P to save as PDF")


if __name__ == "__main__":
    main()
