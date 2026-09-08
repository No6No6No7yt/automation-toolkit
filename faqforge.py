#!/usr/bin/env python3
r"""
FaqForge — a zero-dependency FAQ & schema generator for SEO.
Sells as: "FAQ page creation with schema markup" (€60–€310 content/SEO
category on PeoplePerHour)

Input: a plain text file of questions & answers in the simplest possible
format:

    # Topic: Acme Roofing FAQ
    Q: Do you offer free estimates?
    A: Yes. Every quote is free and valid 30 days.

    Q: How long does a roof replacement take?
    A: Typically 2-3 working days for an average home.

Output (all from one input file):
    1. faq.html        — a clean, styled, self-contained FAQ page
                          (accordion-free: progressive <details> elements,
                          zero JS)
    2. faq-schema.html — JSON-LD FAQPage schema.org markup, ready to paste
                          into the page head (Google rich-result eligible)
    3. faq.csv         — Q&A pairs for import into docs/CRM tools

The buyer hands over a rough Q&A list (usually bullet points from their
support inbox); the deliverable is a publish-ready page + schema.

Usage:
    python faqforge.py faq.txt --title "Acme Roofing FAQ" --outdir out/
    python faqforge.py faq.txt --schema-only   # just the JSON-LD block
"""

import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path


def parse_faq(text: str):
    """Parse Q:/A: pairs. Supports Q and A lines in any reasonable format."""
    entries, topic = [], None
    current_q, current_a = None, []

    def flush():
        nonlocal current_q, current_a
        if current_q is not None:
            answer = " ".join(" ".join(current_a).split())
            if answer:
                entries.append((current_q.strip(), answer))
            else:
                print(f"warn: question without answer skipped: {current_q[:60]}",
                      file=sys.stderr)
        current_q, current_a = None, []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        topic_match = re.match(r"(?:#\s*Topic:|topic:)\s*(.+)", line, re.IGNORECASE)
        q_match = re.match(r"(?:Q(?::|\.)|Question:)\s*(.+)", line, re.IGNORECASE)
        a_match = re.match(r"(?:A(?::|\.)|Answer:)\s*(.+)", line, re.IGNORECASE)
        if topic_match:
            topic = topic_match.group(1).strip()
        elif q_match:
            flush()
            current_q = q_match.group(1).strip()
        elif a_match and current_q is not None:
            current_a.append(a_match.group(1).strip())
        elif current_q is not None:
            # continuation line of the current answer
            current_a.append(line)
        else:
            print(f"warn: ignored line outside Q/A: {line[:60]}", file=sys.stderr)
    flush()
    return topic, entries


CSS = """
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; margin: 0;
       background: #f4f5f8; color: #1d2433; }
.page { max-width: 720px; margin: 32px auto; background: #fff; padding: 40px 48px;
        border-radius: 12px; box-shadow: 0 2px 16px rgba(20,30,60,.08); }
h1 { font-size: 26px; margin: 0 0 6px; }
.meta { color: #7a8299; font-size: 13px; margin-bottom: 28px; }
details { border: 1px solid #e6e9f2; border-radius: 10px; padding: 0; margin: 10px 0; }
summary { cursor: pointer; padding: 15px 18px; font-weight: 600; font-size: 15px;
          list-style: none; display: flex; justify-content: space-between; }
summary::after { content: '+'; color: #4f6df5; font-size: 20px; font-weight: 400; }
details[open] summary::after { content: '–'; }
details[open] summary { border-bottom: 1px solid #eef0f6; }
.answer { padding: 12px 18px 16px; font-size: 14.5px; line-height: 1.55; color: #3a4358; }
footer { margin-top: 32px; font-size: 11.5px; color: #9aa1b5; }
"""


def render_page(topic, entries, title):
    items = []
    for i, (q, a) in enumerate(entries, 1):
        items.append(
            f"<details id='faq-{i}'{' open' if i == 1 else ''}>"
            f"<summary>{html.escape(q)}</summary>"
            f"<div class='answer'>{html.escape(a)}</div></details>")
    return f"""<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{html.escape(title)}</title>
<meta name='description' content='{html.escape(title)} — {len(entries)} frequently asked questions.'>
<style>{CSS}</style></head><body>
<div class='page'>
<h1>{html.escape(title)}</h1>
<div class='meta'>{html.escape(topic) if topic else 'Frequently asked questions'} — {len(entries)} questions</div>
{''.join(items)}
<footer>Generated with FaqForge — self-contained HTML, no scripts.</footer>
</div></body></html>"""


def render_schema(entries, title):
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in entries
        ],
    }
    return ("<script type='application/ld+json'>\n"
            + json.dumps(schema, indent=2, ensure_ascii=False)
            + "\n</script>")


def main():
    parser = argparse.ArgumentParser(description="FAQ page + schema generator.")
    parser.add_argument("input", help="text file with Q:/A: pairs")
    parser.add_argument("--title", default=None, help="page title (default: topic or file name)")
    parser.add_argument("--outdir", default="faq-out", help="output directory")
    parser.add_argument("--schema-only", action="store_true",
                        help="print JSON-LD schema to stdout only")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    topic, entries = parse_faq(text)
    if not entries:
        sys.exit("error: no Q/A pairs found — use 'Q: ...' and 'A: ...' lines")
    title = args.title or topic or Path(args.input).stem.replace("-", " ").title()

    if args.schema_only:
        print(render_schema(entries, title))
        return

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "faq.html").write_text(render_page(topic, entries, title), encoding="utf-8")
    (out / "faq-schema.html").write_text(render_schema(entries, title), encoding="utf-8")
    with open(out / "faq.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["question", "answer"])
        writer.writerows(entries)

    print(f"{len(entries)} Q&A pair(s) parsed" + (f" (topic: {topic})" if topic else ""))
    print(f"outputs -> {out}/faq.html, faq-schema.html, faq.csv")
    print("next: paste faq-schema.html into the <head> of faq.html (or your CMS)")


if __name__ == "__main__":
    main()
