#!/usr/bin/env python3
"""
Demosite generator for the Automation Toolkit.

Builds demos/index.html — the public catalog page. The design goal is
"liquid glass": translucent panels floating over a slowly drifting
gradient field, hairline specular edges, and content that reads like a
person made it, because a person did.

Regenerate after changing tool list or samples:
    python demosite.py
"""

import csv
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DEMOS = ROOT / "demos"
DEMOS.mkdir(exist_ok=True)


def sh(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True,
                       cwd=str(ROOT))
    if r.returncode:
        print(r.stdout, r.stderr)
        sys.exit(f"step failed: {args}")
    return r


# ---------------------------------------------------------------------------
# Catalog copy — written like a person explaining to another person.
# Each entry: tool name, file, what you'd tell a friend it does, market range.
# ---------------------------------------------------------------------------

TOOLS = [
    ("ScrapeKit", "scrapekit.py",
     "Point it at any website and tell it what you want — links, emails, prices, "
     "or anything a regex can describe. It crawls politely and hands you clean JSON or CSV.",
     "€35–345"),
    ("FileForge", "fileforge.py",
     "The folder you're afraid to look at, sorted. Organizes, renames, and finds "
     "duplicates by content — and shows you a preview of everything before it touches a single file.",
     "€85–120"),
    ("PromptFlow", "promptflow.py",
     "Four serious prompt chains (research, content, spec-to-code, self-refine) "
     "with a runner that carries each step's answer into the next. Works with any AI — no API keys, no lock-in.",
     "€105–540"),
    ("LeadMiner", "leadminer.py",
     "Feed it a list of company websites, get back a spreadsheet of contact emails, "
     "phone numbers, and socials. It checks contact pages and filters out the noreply junk automatically.",
     "€30–345"),
    ("APIForge", "apiforge.py",
     "Fetches from any REST API — pagination, retries, auth headers handled — then "
     "syncs it on a schedule, keeping only the new rows. The monitor mode watches an endpoint "
     "and exits non-zero when something's off, so cron can alert you.",
     "€85–385"),
    ("ReportForge", "reportforge.py",
     "Send it a CSV, get back a report that looks like an analyst made it: KPI cards, "
     "stats, charts, segment breakdowns. One self-contained HTML file you can print to PDF.",
     "€30–310"),
    ("CSVKit", "csvkit.py",
     "For the messy spreadsheet problems: merge files with different columns, kill "
     "duplicates, clean whitespace and junk values, pivot long into wide, and diff two exports row by row.",
     "€15–60"),
    ("MediaSift", "mediasift.py",
     "Reads image dimensions straight from the file bytes — no image library needed — "
     "then renames and sorts your photo library by date, orientation, or aspect ratio. Preview-first, like everything else here.",
     "€10–35"),
    ("SiteDoctor", "sitedoctor.py",
     "Crawls a site like a picky SEO consultant and writes up everything it finds: "
     "broken links, missing titles and descriptions, absent alt text, duplicate pages, slow responses. "
     "Delivered as a severity-colored report you can hand to a client.",
     "€10–180"),
    ("FaqForge", "faqforge.py",
     "Paste a rough list of questions and answers, get a finished FAQ page — styled, "
     "accordioned, with proper schema.org markup so Google can feature it.",
     "€60–310"),
    ("MailForge", "mailforge.py",
     "Mail merge without the privacy nightmare: takes a template and a CSV, produces "
     "personalized drafts as .eml files you open, review, and send yourself. It never touches SMTP — "
     "and it refuses to send 'Dear {name}'.",
     "€25–115"),
    ("TaskLoop", "taskloop.py",
     "The anti-Zapier: run any script on a schedule with proper logs, retries, and "
     "backoff — on your machine, with zero monthly fees. Generates its own autostart config for Windows, macOS, or Linux.",
     "€20–115"),
]


# ---------------------------------------------------------------------------
# Sample generation — real outputs from the real tools
# ---------------------------------------------------------------------------

def make_samples():
    random.seed(7)
    with open(DEMOS / "sample-sales.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "revenue", "units", "product"])
        for i in range(200):
            w.writerow(["North South East West".split()[i % 4],
                        round(random.gauss(4800, 1200), 2),
                        random.randint(1, 50), f"SKU-{i % 7}"])
    sh("reportforge.py", "demos/sample-sales.csv",
       "--title", "Q3 Regional Sales — Sample Report",
       "--group-by", "region", "--out", "demos/sample-report.html")

    (DEMOS / "sample-faq.txt").write_text(
        "# Topic: Sample Company\n"
        "Q: Do you offer free estimates?\n"
        "A: Yes. Every quote is free and valid for 30 days.\n\n"
        "Q: How long does a project take?\n"
        "A: Typically 2-3 working days from kickoff.\n\n"
        "Q: What areas do you serve?\n"
        "A: The greater metro area and suburbs within 50 miles.\n",
        encoding="utf-8")
    sh("faqforge.py", "demos/sample-faq.txt", "--title", "Sample Company FAQ",
       "--outdir", "demos/sample-faq")

    sh("sitedoctor.py", "https://example.com", "--depth", "0", "--limit", "2",
       "--report", "demos/sample-audit.html")

    (DEMOS / "sample-template.txt").write_text(
        "Subject: Your order {order_id} shipped, {first_name}!\n"
        "Body:\nHi {first_name},\n\n"
        "Your order {order_id} shipped today. Track it anytime from your account.\n\n"
        "- The Sample Shop\n", encoding="utf-8")
    (DEMOS / "sample-rcv.csv").write_text(
        "email,first_name,order_id\nbuyer@example.org,Bob,#10241\n"
        "shopper@example.org,Maria,#10242\n", encoding="utf-8")
    sh("mailforge.py", "demos/sample-template.txt", "demos/sample-rcv.csv",
       "--sheet", "--out", "demos/sample-mail")

    return [
        ("ReportForge — sample insight report", "demos/sample-report.html"),
        ("SiteDoctor — sample audit", "demos/sample-audit.html"),
        ("FaqForge — sample FAQ page", "demos/sample-faq/faq.html"),
        ("MailForge — sample draft sheet", "demos/sample-mail/review.html"),
    ]


# ---------------------------------------------------------------------------
# The page. Liquid-glass layers, outside in:
#   1. A gradient field with three slow-drifting orbs (the "liquid")
#   2. A soft noise grain so the glass has something to refract
#   3. Glass panels: translucent fill, 1px specular top edge, blurred backdrop
#   4. Content: human copy, tabular numbers, generous rhythm
# ---------------------------------------------------------------------------

def build_page(samples):
    cards = "\n".join(
        f"""      <article class="glass card">
        <h3>{name}</h3>
        <code>{filename}</code>
        <p>{desc}</p>
        <span class="price">sells for {price}</span>
      </article>"""
        for name, filename, desc, price in TOOLS)

    frames = "\n".join(
        f"""    <section class="glass sample">
      <div class="sample-head">
        <h4>{title}</h4>
        <span>generated by the tool itself, just now</span>
      </div>
      <iframe src="{src}" loading="lazy" title="{title}"></iframe>
    </section>"""
        for title, src in samples)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The 12-Tool Automation Toolkit</title>
<style>
  :root {{
    --ink: #eef1f8;
    --ink-dim: #b9c0d4;
    --ink-faint: #8d95ac;
    --glass: rgba(255, 255, 255, 0.055);
    --glass-edge: rgba(255, 255, 255, 0.14);
    --glass-blur: 22px;
    --accent: #8fb7ff;
  }}

  * {{ box-sizing: border-box; }}

  body {{
    margin: 0;
    min-height: 100vh;
    font-family: -apple-system, "SF Pro Display", "Segoe UI", Roboto,
                 "Helvetica Neue", sans-serif;
    color: var(--ink);
    background: #0a0d16;
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
  }}

  /* --- the liquid: a drifting gradient field ---------------------------- */

  .liquid {{
    position: fixed;
    inset: 0;
    z-index: -2;
    overflow: hidden;
    background: linear-gradient(160deg, #0c1020 0%, #0a0d16 55%, #101528 100%);
  }}
  .liquid::after {{
    /* film grain: the glass needs texture to refract */
    content: "";
    position: absolute;
    inset: -50%;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.05'/%3E%3C/svg%3E");
    pointer-events: none;
  }}
  .orb {{
    position: absolute;
    border-radius: 50%;
    filter: blur(90px);
    opacity: 0.55;
    will-change: transform;
  }}
  .orb.a {{ width: 55vmax; height: 55vmax; left: -12vmax; top: -18vmax;
           background: radial-gradient(circle, #2743c7 0%, transparent 70%);
           animation: drift-a 38s ease-in-out infinite alternate; }}
  .orb.b {{ width: 48vmax; height: 48vmax; right: -16vmax; top: 30vh;
           background: radial-gradient(circle, #6d28a8 0%, transparent 70%);
           animation: drift-b 46s ease-in-out infinite alternate; }}
  .orb.c {{ width: 40vmax; height: 40vmax; left: 25vw; bottom: -20vmax;
           background: radial-gradient(circle, #0e6e5c 0%, transparent 70%);
           animation: drift-c 52s ease-in-out infinite alternate; }}

  @keyframes drift-a {{ from {{ transform: translate(0, 0) scale(1); }}
                        to   {{ transform: translate(14vw, 10vh) scale(1.15); }} }}
  @keyframes drift-b {{ from {{ transform: translate(0, 0) scale(1.1); }}
                        to   {{ transform: translate(-12vw, -14vh) scale(0.95); }} }}
  @keyframes drift-c {{ from {{ transform: translate(0, 0) scale(0.9); }}
                        to   {{ transform: translate(10vw, -8vh) scale(1.2); }} }}

  @media (prefers-reduced-motion: reduce) {{
    .orb {{ animation: none; }}
  }}

  /* --- glass panels ------------------------------------------------------ */

  .glass {{
    position: relative;
    background: var(--glass);
    border: 1px solid var(--glass-edge);
    border-radius: 24px;
    -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(150%);
    backdrop-filter: blur(var(--glass-blur)) saturate(150%);
    box-shadow:
      0 24px 60px rgba(4, 8, 20, 0.5),
      inset 0 1px 0 rgba(255, 255, 255, 0.1);
    overflow: hidden;
  }}
  .glass::before {{
    /* specular top edge — the thing that reads as 'glass' */
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(
      180deg,
      rgba(255, 255, 255, 0.12) 0%,
      rgba(255, 255, 255, 0.02) 18%,
      transparent 40%);
    pointer-events: none;
  }}

  /* --- layout & type ------------------------------------------------------ */

  .wrap {{ max-width: 1060px; margin: 0 auto; padding: 88px 24px 120px; }}

  header.hero {{ text-align: center; margin-bottom: 72px; }}
  .hero .eyebrow {{
    display: inline-block;
    font-size: 13px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--ink-faint);
    padding: 8px 18px;
    border-radius: 999px;
    border: 1px solid var(--glass-edge);
    background: rgba(255, 255, 255, 0.04);
    margin-bottom: 26px;
  }}
  .hero h1 {{
    font-size: clamp(38px, 6vw, 66px);
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.05;
    margin: 0 0 20px;
    background: linear-gradient(180deg, #ffffff 30%, #a8b6d8 100%);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }}
  .hero p {{
    max-width: 640px;
    margin: 0 auto;
    font-size: 18px;
    line-height: 1.65;
    color: var(--ink-dim);
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 18px;
    margin-bottom: 96px;
  }}

  .card {{ padding: 30px 32px 26px; transition: transform 0.35s ease, border-color 0.35s ease; }}
  .card:hover {{ transform: translateY(-4px); border-color: rgba(255, 255, 255, 0.24); }}
  .card h3 {{ margin: 0 0 10px; font-size: 21px; letter-spacing: -0.01em; }}
  .card code {{
    display: inline-block;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 12px;
    color: var(--accent);
    background: rgba(143, 183, 255, 0.08);
    border: 1px solid rgba(143, 183, 255, 0.15);
    padding: 3px 10px;
    border-radius: 7px;
    margin-bottom: 14px;
  }}
  .card p {{ margin: 0 0 18px; font-size: 14.5px; line-height: 1.6; color: var(--ink-dim); }}
  .price {{
    font-size: 12px;
    font-weight: 600;
    color: #8ce6b0;
    background: rgba(140, 230, 176, 0.09);
    border: 1px solid rgba(140, 230, 176, 0.18);
    padding: 4px 12px;
    border-radius: 999px;
    white-space: nowrap;
  }}

  .samples-title {{ text-align: center; margin-bottom: 8px; }}
  .samples-title h2 {{
    font-size: clamp(26px, 3.5vw, 36px);
    letter-spacing: -0.015em;
    margin: 0;
  }}
  .samples-sub {{
    text-align: center;
    color: var(--ink-faint);
    font-size: 15px;
    margin: 0 0 36px;
  }}

  .sample {{ margin-bottom: 22px; }}
  .sample-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 16px;
    padding: 22px 30px;
    flex-wrap: wrap;
  }}
  .sample-head h4 {{ margin: 0; font-size: 17px; }}
  .sample-head span {{ font-size: 12.5px; color: var(--ink-faint); }}
  .sample iframe {{ width: 100%; height: 480px; border: 0; display: block; background: #fff; }}

  footer {{
    text-align: center;
    color: var(--ink-faint);
    font-size: 13px;
    margin-top: 80px;
  }}
  footer a {{ color: var(--accent); text-decoration: none; }}
</style>
</head>
<body>

<div class="liquid" aria-hidden="true">
  <div class="orb a"></div>
  <div class="orb b"></div>
  <div class="orb c"></div>
</div>

<div class="wrap">

  <header class="hero">
    <span class="eyebrow">plain Python · zero dependencies · yours to keep</span>
    <h1>Twelve tools that do<br>the work people pay for.</h1>
    <p>
      Scraping, file wrangling, lead lists, reports, audits, mail merges, scheduled
      jobs — each one a single Python file with nothing to install, previewing every
      change before it happens. Built, tested, and documented end to end.
    </p>
  </header>

  <div class="grid">
{cards}
  </div>

  <div class="samples-title">
    <h2>Real samples, not screenshots</h2>
  </div>
  <p class="samples-sub">Everything below was generated by the tools themselves, on this machine, right now.</p>

{frames}

  <footer>
    The <a href="https://github.com/No6No6No7yt/automation-toolkit">Automation Toolkit</a> —
    every tool dry-run safe, every output reproducible.
  </footer>

</div>
</body>
</html>
"""


def main():
    samples = make_samples()
    (DEMOS / "index.html").write_text(build_page(samples), encoding="utf-8")
    print(f"built demos/index.html — {len(TOOLS)} tools, {len(samples)} live samples")
    print(f"open {DEMOS / 'index.html'}")


if __name__ == "__main__":
    main()
