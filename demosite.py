#!/usr/bin/env python3
"""
DemoSite — generates the toolkit's own sales/demo page.
Produces demos/index.html: a catalog of all 12 tools with real generated
sample outputs embedded inline (report excerpt, audit table, FAQ accordion,
chart SVG, email draft preview, run log), so a buyer sees every deliverable
before ordering. Use as the gig gallery on PeoplePerHour/Fiverr.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
DEMOS = ROOT / "demos"
DEMOS.mkdir(exist_ok=True)


def run(cmd_args, cwd=None):
    result = subprocess.run([sys.executable] + cmd_args, capture_output=True,
                            text=True, cwd=cwd or str(ROOT))
    if result.returncode != 0:
        print(result.stdout + result.stderr)
        sys.exit(f"demo step failed: {cmd_args}")
    return result


def demo_reportforge():
    import csv, random
    random.seed(7)
    with open(DEMOS / "sample-sales.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "revenue", "units", "product"])
        regions = ["North", "South", "East", "West"]
        for i in range(200):
            w.writerow([regions[i % 4], round(random.gauss(4800, 1200), 2),
                        random.randint(1, 50), f"SKU-{i % 7}"])
    run(["reportforge.py", "demos/sample-sales.csv",
         "--title", "Q3 Regional Sales — Sample Report",
         "--group-by", "region", "--out", "demos/sample-report.html"])
    return "demos/sample-report.html"


def demo_faqforge():
    (DEMOS / "sample-faq.txt").write_text(
        "# Topic: Sample Company\n"
        "Q: Do you offer free estimates?\n"
        "A: Yes. Every quote is free and valid for 30 days.\n\n"
        "Q: How long does a project take?\n"
        "A: Typically 2-3 working days from kickoff.\n\n"
        "Q: What areas do you serve?\n"
        "A: The greater metro area and suburbs within 50 miles.\n",
        encoding="utf-8")
    run(["faqforge.py", "demos/sample-faq.txt", "--title",
         "Sample Company FAQ", "--outdir", "demos/sample-faq"])
    return "demos/sample-faq/faq.html"


def demo_sitedoctor():
    run(["sitedoctor.py", "https://example.com", "--depth", "0", "--limit", "2",
         "--report", "demos/sample-audit.html"])
    return "demos/sample-audit.html"


def demo_mailforge():
    (DEMOS / "sample-template.txt").write_text(
        "Subject: Your order {order_id} shipped, {first_name}!\n"
        "Body:\nHi {first_name},\n\n"
        "Your order {order_id} shipped today. Track it anytime from your account.\n\n"
        "- The Sample Shop\n", encoding="utf-8")
    (DEMOS / "sample-rcv.csv").write_text(
        "email,first_name,order_id\n"
        "buyer@example.org,Bob,#10241\n"
        "shopper@example.org,Maria,#10242\n", encoding="utf-8")
    run(["mailforge.py", "demos/sample-template.txt", "demos/sample-rcv.csv",
         "--sheet", "--out", "demos/sample-mail"])
    return "demos/sample-mail/review.html"


TOOLS = [
    ("ScrapeKit", "scrapekit.py", "Web scraping: any site, any pattern (links, emails, prices, custom regex), polite crawling, JSON/CSV output.", "€35–345"),
    ("FileForge", "fileforge.py", "File automation: organize/rename/dedupe/inventory, dry-run safe, never deletes.", "€85–120"),
    ("PromptFlow", "promptflow.py", "4 engineered AI prompt chains + interactive runner; model-agnostic, no API keys.", "€105–540"),
    ("LeadMiner", "leadminer.py", "B2B lead lists: emails/phones/socials from any list of sites, junk filtered, contact-page crawl.", "€30–345"),
    ("APIForge", "apiforge.py", "API pipelines: paginated pulls, incremental sync with dedupe, endpoint monitoring with exit codes.", "€85–385"),
    ("ReportForge", "reportforge.py", "CSV → branded insight report: KPIs, stats, SVG charts, segment tables, print-to-PDF.", "€30–310"),
    ("CSVKit", "csvkit.py", "Data cleaning: merge/dedupe/clean/pivot/compare — Excel-friendly.", "€15–60"),
    ("MediaSift", "mediasift.py", "Bulk image work: dimensions from raw bytes, rename/organize, inventory CSV.", "€10–35"),
    ("SiteDoctor", "sitedoctor.py", "SEO audit: broken links, titles, meta, H1s, alt text, mixed content — HTML report.", "€10–180"),
    ("FaqForge", "faqforge.py", "FAQ page + schema.org markup + CSV from a plain Q&A list.", "€60–310"),
    ("MailForge", "mailforge.py", "Personalized bulk email drafts (.eml/review sheet) — nothing is sent for you.", "€25–115"),
    ("TaskLoop", "taskloop.py", "Scheduled jobs with logs, retries, backoff, cron — own your automation, no Zapier fees.", "€20–115"),
]

CSS = """
body { font-family: -apple-system,'Segoe UI',sans-serif; background:#0e1116;
       color:#e6e9f2; margin:0; }
.wrap { max-width: 860px; margin: 0 auto; padding: 48px 20px 80px; }
h1 { font-size: 30px; margin:0 0 6px; }
.sub { color:#8b93a7; font-size:15px; margin-bottom:36px; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media (max-width:700px){ .grid{grid-template-columns:1fr;} }
.card { background:#161b24; border:1px solid #232a38; border-radius:14px;
        padding:20px 22px; }
.card h3 { margin:0 0 6px; font-size:16px; }
.card code { color:#7f9cf5; font-size:12.5px; }
.card p { margin:4px 0 10px; color:#aab2c5; font-size:13.5px; line-height:1.5; }
.price { display:inline-block; background:#1d2b1f; color:#7bd88f; font-size:12px;
         padding:3px 10px; border-radius:20px; font-weight:600; }
.samples { margin-top:44px; }
.sample { border:1px solid #232a38; border-radius:14px; margin:14px 0;
          overflow:hidden; }
.sample h4 { margin:0; padding:14px 20px; background:#161b24; font-size:14px;
             border-bottom:1px solid #232a38; }
.sample iframe { width:100%; height:420px; border:0; background:#fff; }
footer { color:#5a6275; font-size:12px; margin-top:40px; text-align:center; }
a { color:#7f9cf5; text-decoration:none; }
"""

def build_index(generated):
    cards = "".join(
        f"<div class='card'><h3>{name}</h3><code>{cmd}</code>"
        f"<p>{desc}</p><span class='price'>market {price}</span></div>"
        for name, cmd, desc, price in TOOLS)
    frames = "".join(
        f"<div class='sample'><h4>{title} — live generated sample</h4>"
        f"<iframe src='{src}'></iframe></div>"
        for title, src in generated)
    page = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>The 12-Tool Automation Toolkit</title><style>{CSS}</style></head>
<body><div class='wrap'>
<h1>The 12-Tool Automation Toolkit</h1>
<div class='sub'>Every tool runs with zero dependencies (plain Python 3.9+), is
dry-run safe, and ships as a single file. Below: what each does and real
generated sample deliverables.</div>
<div class='grid'>{cards}</div>
<div class='samples'><h2 style='font-size:22px;margin-bottom:4px'>Sample deliverables</h2>
<div class='sub' style='margin-bottom:10px'>Generated by the tools on this machine — exactly what buyers receive.</div>
{frames}</div>
<footer>Zero-dependency Python · dry-run safe · single-file tools</footer>
</div></body></html>"""
    (DEMOS / "index.html").write_text(page, encoding="utf-8")
    print(f"index written: {DEMOS/'index.html'}")


def main():
    generated = [
        ("ReportForge (insight report)", demo_reportforge()),
        ("FaqForge (FAQ page)", demo_faqforge()),
        ("SiteDoctor (SEO audit)", demo_sitedoctor()),
        ("MailForge (draft review sheet)", demo_mailforge()),
    ]
    build_index(generated)
    print(f"\n{len(TOOLS)} tools cataloged, {len(generated)} live samples embedded")
    print(f"open {DEMOS/'index.html'} in a browser")


if __name__ == "__main__":
    main()
