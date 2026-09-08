#!/usr/bin/env python3
r"""
MailForge — a zero-dependency bulk email draft generator.
Sells as: "email template / mail merge / newsletter drafting" (€25–€115
on PeoplePerHour) — WITHOUT sending anything (no SMTP, no accounts, no
spam risk; that's the compliant pitch)

What it does:
    Reads a CSV of recipients + a template file with {placeholders},
    produces one personalized draft per row as:
      - .txt files in a folder (ready to paste anywhere), or
      - a single combined review sheet, or
      - an .eml file per row (opens pre-addressed in Outlook/Apple Mail/
        Thunderbird — buyer reviews and hits send themselves)

The {placeholders} map directly to CSV columns; a missing value is a hard
error (never silently send "Dear {name}"). Includes per-row validation
warnings for empty subjects or suspicious addresses.

Usage:
    python mailforge.py template.txt recipients.csv --out drafts/
    python mailforge.py template.txt recipients.csv --eml --out drafts/
    python mailforge.py template.txt recipients.csv --sheet review.html

Template format (template.txt):
    Subject: Your invoice from ACME, {name}
    Body:
    Hi {name},

    Your order {order_id} shipped on {ship_date}...

    Best,
    ACME
"""

import argparse
import csv
import datetime
import email.utils
import html
import re
import sys
from email.message import EmailMessage
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{([a-z_][a-z0-9_]*)\}", re.IGNORECASE)
SUSPICIOUS_EMAIL = re.compile(r"(noreply|no-reply|donotreply|test|example\.com)", re.IGNORECASE)


def parse_template(text: str):
    """Split template into (subject_template, body_template)."""
    subject_match = re.match(r"^\s*Subject:\s*(.+)\n", text, re.IGNORECASE)
    if subject_match:
        subject = subject_match.group(1).strip()
        body = text[subject_match.end():].strip()
        body = re.sub(r"^\s*Body:\s*\n", "", body, count=1, flags=re.IGNORECASE)
        return subject, body
    sys.exit("error: template must start with a 'Subject:' line")


def render(template: str, values: dict, strict: bool) -> str:
    def substitute(match):
        key = match.group(1)
        if key not in values:
            if strict:
                sys.exit(f"error: template uses {{{key}}} but CSV has no "
                         f"column '{key}' (columns: {sorted(values)})")
            return match.group(0)
        value = str(values[key]).strip()
        if not value and strict:
            raise KeyError(key)
        return value
    try:
        return PLACEHOLDER_RE.sub(substitute, template)
    except KeyError as e:
        sys.exit(f"error: empty value for placeholder {e} in some row — "
                 "fill the CSV or use --allow-missing")


def cmd_run(args):
    template_text = Path(args.template).read_text(encoding="utf-8")
    subject_tpl, body_tpl = parse_template(template_text)

    with open(args.recipients, newline="", encoding="utf-8-sig") as f:
        rows = [dict(r) for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]
    if not rows:
        sys.exit("error: recipients CSV has no data rows")

    strict = not args.allow_missing
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    warnings, written = [], 0
    emls, sheet_rows = [], []
    for i, row in enumerate(rows, 1):
        values = {k: (v or "") for k, v in row.items()}
        subject = render(subject_tpl, values, strict)
        body = render(body_tpl, values, strict)

        to_addr = (values.get("email") or values.get("to") or "").strip()
        if not to_addr:
            warnings.append(f"row {i}: no 'email'/'to' column value — draft written without address")
        elif not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", to_addr):
            warnings.append(f"row {i}: suspicious address '{to_addr}'")
        elif SUSPICIOUS_EMAIL.search(to_addr) and not args.allow_suspicious:
            warnings.append(f"row {i}: address '{to_addr}' looks like a test/noreply address")

        if args.sheet:
            sheet_rows.append((to_addr, subject, body))
        elif args.eml:
            msg = EmailMessage()
            msg["To"] = to_addr or "(no address)"
            msg["Subject"] = subject
            msg["From"] = args.sender or "(set --sender)"
            msg["Date"] = email.utils.format_datetime(datetime.datetime.now())
            msg.set_content(body)
            safe = re.sub(r"[^a-z0-9]+", "_", (to_addr or f"row{i}").lower())[:40]
            eml_path = out_dir / f"{i:03d}_{safe}.eml"
            eml_path.write_bytes(msg.as_bytes())
            written += 1
        else:
            text_path = out_dir / f"{i:03d}.txt"
            text_path.write_text(f"To: {to_addr}\nSubject: {subject}\n\n{body}",
                                 encoding="utf-8")
            written += 1
        emls.append((to_addr, subject))

    for warning in warnings:
        print(f"  warn: {warning}", file=sys.stderr)

    if args.sheet:
        page = render_sheet(sheet_rows)
        (out_dir / "review.html").write_text(page, encoding="utf-8")
        print(f"{len(sheet_rows)} draft(s) -> {out_dir/'review.html'} — review before use")
    else:
        mode = ".eml files (open in a mail client, review, send)" if args.eml \
            else ".txt drafts"
        print(f"{written} personalized draft(s) -> {out_dir} as {mode}")
    if warnings:
        print(f"{len(warnings)} warning(s) — check addresses before sending", file=sys.stderr)


def render_sheet(rows):
    items = "".join(
        f"<div class='mail'><div class='hdr'>To: {html.escape(to or '—')} &nbsp;|&nbsp; "
        f"<b>{html.escape(subject)}</b></div><pre>{html.escape(body)}</pre></div>"
        for to, subject, body in rows)
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Mail draft review</title>
<style>
body {{ font-family: -apple-system,'Segoe UI',sans-serif; background:#f4f5f8; margin:0; }}
.wrap {{ max-width:760px; margin:24px auto; padding:0 12px; }}
h1 {{ font-size:20px; }}
.mail {{ background:#fff; border-radius:10px; padding:16px 20px; margin:12px 0;
        box-shadow:0 2px 10px rgba(20,30,60,.07); }}
.hdr {{ font-size:12.5px; color:#7a8299; margin-bottom:8px; }}
pre {{ white-space:pre-wrap; font-family:inherit; font-size:14px; margin:0; }}
</style></head><body><div class='wrap'>
<h1>{len(rows)} mail drafts — review</h1>
{items}
</div></body></html>"""


def main():
    parser = argparse.ArgumentParser(
        prog="mailforge",
        description="Personalized bulk email DRAFTS from template + CSV (nothing is sent).")
    parser.add_argument("template", help="template file starting with 'Subject:'")
    parser.add_argument("recipients", help="CSV with recipient rows (needs 'email' column)")
    parser.add_argument("--out", default="mail-drafts", help="output directory")
    parser.add_argument("--eml", action="store_true",
                        help="write .eml files instead of .txt")
    parser.add_argument("--sheet", action="store_true",
                        help="write one review.html instead of per-row files")
    parser.add_argument("--sender", help="From: address for .eml mode")
    parser.add_argument("--allow-missing", action="store_true",
                        help="leave unresolved placeholders instead of erroring")
    parser.add_argument("--allow-suspicious", action="store_true",
                        help="don't warn on test/noreply-looking addresses")
    args = parser.parse_args()
    cmd_run(args)


if __name__ == "__main__":
    main()
