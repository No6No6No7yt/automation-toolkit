# Sellable Toolkit — 3 Ready-to-Deliver Products

Everything here is **tested, working, zero-dependency Python** (3.9+, standard
library only — customers never need to `pip install` anything). Each product
matches a proven paid-service category on PeoplePerHour/Fiverr with the live
market price observed in research on 2026-09-08.

## Products

| # | File | Sell as | Market price observed |
|---|------|---------|-----------------------|
| 1 | `scrapekit.py` | "Custom data extraction / web scraping from any website" | €35–€345 |
| 2 | `fileforge.py` | "Python task automation / file organization scripts" | €85–€120 |
| 3 | `promptflow.py` | "Professional prompt chains / AI workflow systems" | €105–€420 |
| 4 | `leadminer.py` | "Targeted B2B lead generation lists" | €30–€70 per 150–500 leads; custom tools €345 |
| 5 | `apiforge.py` | "API integration / data pipeline scripts" | €85–€175 (AI workflow integration €175–€385) |
| 6 | `reportforge.py` | "Data research / insights report with charts" | €30–€310 |
| 7 | `csvkit.py` | "Data cleansing / merge spreadsheets / dedupe" | €15–€60 (highest-volume category) |
| 8 | `mediasift.py` | "Bulk image renaming / photo library organization" | €10–€35 per job, recurring |
| 9 | `sitedoctor.py` | "Website SEO audit / broken link report" | €10–€180 |
| 10 | `faqforge.py` | "FAQ page creation with schema markup" | €60–€310 |
| 11 | `mailforge.py` | "Email template / mail merge / newsletter drafting" | €25–€115 |
| 12 | `taskloop.py` | "Automation scripts + scheduling setup (no Zapier fees)" | €20–€115 |

All three were tested end-to-end on 2026-09-08 (see Test log below).

---

## 1. ScrapeKit (`scrapekit.py`)

Zero-dependency polite scraper: single-page or crawling (same-site, configurable
depth), extraction of links / emails / images / page text / **any custom regex**,
robots.txt respected, JSON/CSV/TXT output.

```bash
python scrapekit.py https://example.com --emails --depth 2 --out emails.json
python scrapekit.py https://shop.example.com --select "€\d+[.,]\d{2}" --out prices.csv
```

**Delivery model per listing:** flat price for the tool + per-configuration of
patterns for the customer's target site. Custom regex extraction is the
differentiator — most €35 gigs deliver a plain link list; the `--select` mode
delivers structured field extraction (prices, phone numbers, SKUs).

## 2. FileForge (`fileforge.py`)

File & folder automation: organize by extension/category/date, batch-rename
with patterns (`vacation-{n:03}{ext}`), content-hash duplicate finder with
quarantine-move, CSV/JSON folder inventory reports. **Dry-run by default,
never deletes** — that's the safety pitch that wins business buyers.

```bash
python fileforge.py organize ~/Downloads --by category --apply
python fileforge.py dedupe ~/Photos --move-dupes ~/duplicates --apply
python fileforge.py report ~/project --format csv --out inventory.csv
```

## 3. APIForge (`apiforge.py`)

REST API toolkit: **pull** (paginated fetch → JSON/CSV with nested-key
flattening), **sync** (scheduled incremental pulls with primary-key dedupe
into a timestamped JSONL store), **monitor** (watch any endpoint value;
exit codes for cron/alerting integrations). Handles auth headers, query
params, page/offset pagination, retries with backoff.

```bash
python apiforge.py pull https://api.example.com/items --page-param page --pages 5 --csv items.csv
python apiforge.py sync https://api.example.com/orders --id-field id --every 900 --out store.jsonl
python apiforge.py monitor https://api.example.com/status --jq-path "data.state" --expect ok --every 60
```

**Delivery model per listing:** API integration gigs pay €85–€175; the sync
(incremental data pipeline) flavor sells into the €175–€385 AI workflow
integration tier. Exit codes make the monitor embeddable in customers' cron
jobs and alerting systems — that's the upsell over a one-off fetch script.

## 4. TaskLoop (`taskloop.py`)

Scheduled job runner: interval (`--every 900`) or full cron-style
scheduling (`--cron '0 9 * * 1-5'`), JSONL run history (timestamp, exit
code, duration, output tail, retry count), failure retries with
exponential backoff, stale-lock protection, and a `startup` command that
prints ready-to-use OS-native autostart config (Task Scheduler XML /
launchd plist / crontab line) — printed only, never installed. The pitch
vs Zapier/n8n gigs: own the automation, no accounts, no monthly fees.

```bash
python taskloop.py run "python apiforge.py sync https://api.example.com/items --id-field id --every 900 --out store.jsonl" --every 1800
python taskloop.py run "python backup.py" --cron "0 3 * * *"
python taskloop.py log --failures --verbose
python taskloop.py startup "python taskloop.py run \"python job.py\" --every 900"
```

**Delivery model per listing:** pairs with apiforge/scrapekit for recurring
data jobs — 'scheduled scraper with logs and auto-restart' sells at the top
of the €20–€115 automation band. The `log` command gives buyers proof of
every run.

## 5. MailForge (`mailforge.py`)

Personalized bulk-email draft generator: template file (`Subject:` + body
with `{placeholders}`) + recipients CSV → one draft per row. Three output
modes: `.txt` drafts, **`.eml` files** (open pre-addressed in
Outlook/Thunderbird/Apple Mail — buyer reviews and hits send), or a single
`review.html` sheet. Never sends anything — no SMTP, no accounts, no
compliance risk (that's the honest pitch). Hard-errors on unknown
placeholders (never "Dear {name}"), warns on noreply/test-looking
addresses.

```bash
python mailforge.py template.txt recipients.csv --eml --sender you@co.com --out drafts/
```

**Delivery model per listing:** mail-merge gigs (€25–€115) where the buyer
supplies template + list and receives personalized, review-ready drafts.
The .eml mode is the differentiator — most gigs deliver a spreadsheet,
this delivers openable mail files.

## 5. FaqForge (`faqforge.py`)

FAQ page + SEO schema generator: buyer sends a rough Q&A list (plain text,
`Q:`/`A:` lines), gets three deliverables from one run — a styled
self-contained FAQ page (zero-JS `<details>` accordions), Google
rich-result-eligible JSON-LD `FAQPage` schema.org markup, and a CSV of the
pairs. Handles multi-line answers, `# Topic:` headers, and warns on
orphan questions instead of guessing.

```bash
python faqforge.py client-questions.txt --title "Acme Roofing FAQ" --outdir faq/
```

**Delivery model per listing:** "I'll create an FAQ page with schema
markup for your site" — €60 base, higher for migration work (existing
support docs → structured FAQ). Fast turnaround: input to deliverable in
minutes, sells in the €60–€310 content/SEO band.

## 5. SiteDoctor (`sitedoctor.py`)

Website SEO & health auditor: crawls one site (configurable depth/limit,
rate-limited), checks every page for broken links, missing/long titles and
meta descriptions, missing H1s or multiple H1s, images without alt text,
mixed http:// content on https:// pages, duplicate titles/descriptions,
slow responses, and link-orphans. Output: console summary + self-contained
HTML audit report (print-to-PDF, severity color-coded) with per-issue fix
suggestions.

```bash
python sitedoctor.py https://clientsite.com --depth 2 --limit 40 --report audit.html
```

**Delivery model per listing:** "website audit report" gigs at €10–€60; the
full categorized report with severities sells at the €100–€180 end. Recurring
upsell: re-run monthly after fixes (monitor-style retainer).

## 5. MediaSift (`mediasift.py`)

Bulk image toolkit that reads **real image headers from raw bytes** (JPEG
SOF markers, PNG IHDR, GIF, BMP) — dimensions, megapixels, aspect,
orientation — with zero dependencies. Subcommands: **info** (inventory to
CSV), **rename** (smart patterns: `{date}`, `{n}`, `{wxh}`), **organize**
(by date/orientation/aspect: panorama/landscape/square/portrait folders),
**resize** (generates a ready-to-run command sheet per OS from the actual
file inventory). Dry-run by default.

```bash
python mediasift.py info ~/photos --csv inventory.csv
python mediasift.py rename ~/photos --pattern "{date}_{n:03}" --apply
python mediasift.py organize ~/photos --by aspect --apply
```

**Delivery model per listing:** photo-library cleanup gigs (€10–€35) where
the seller delivers the organized/renamed library plus the CSV inventory.
Recurring: shops with product image folders.

## 5. CSVKit (`csvkit.py`)

CSV cleaning & merging toolkit — the highest-volume data category on freelance
platforms. Five subcommands: **merge** (combine CSVs with different column
orders, globs supported), **dedupe** (full-row or by key columns, case-
insensitive), **clean** (trim, collapse whitespace, normalize N/A/NULL/
None/- to blank, email normalization, optional drop-rows-missing), **pivot**
(long→wide reshape summing values), **compare** (diff two exports by id
column → added/removed/changed CSV). Excel-friendly BOM handling both ways.

```bash
python csvkit.py merge jan.csv feb.csv mar.csv --out q1.csv --dedupe
python csvkit.py dedupe customers.csv --key email --out clean.csv
python csvkit.py clean messy.csv --emails --out clean.csv
python csvkit.py pivot long.csv --key date --spread region --value sales --out wide.csv
python csvkit.py compare old.csv new.csv --id email --out changes.csv
```

**Delivery model per listing:** cheap gigs (€15–€25) = one-shot merge/dedupe
jobs using this tool; the pivot/compare commands sell into recurring data
pipeline work. This is the volume product — most orders, lowest price.

## 5. ReportForge (`reportforge.py`)

CSV → styled insight report: reads any CSV (Excel exports to CSV in one
click), computes numeric stats (sum/mean/quartiles) and categorical top-N,
renders inline SVG bar charts and histograms — no JS libraries — and emits
one self-contained HTML file. Buyer opens it in any browser and Ctrl+P's
to PDF. `--group-by` adds per-segment summary tables.

```bash
python reportforge.py sales.csv --title "Q3 Sales" --group-by region --out report.html
```

**Delivery model per listing:** "send spreadsheet → receive branded insights
report" (€30–€60 base, €310 for the premium tier). Zero-dependency HTML
output is the pitch: no software to install, report works offline forever.

## 5. LeadMiner (`leadminer.py`)

B2B lead-list builder: feed it a text file of websites, it visits each (plus
contact/about pages one level deep), extracts emails, phone numbers, social
profiles and company names, filters junk addresses (noreply/footer/abuse),
dedupes, and outputs an Excel-friendly CSV lead list.

```bash
python leadminer.py sites.txt --out leads.csv --depth 1
```

**Delivery model per listing:** flat rate per batch of sites — the PeoplePerHour
market pays €30–€70 per 150–500 leads. Junk-email filtering and contact-page
crawling are the differentiators versus €10 lead gigs.

## 4. PromptFlow (`promptflow.py`)

A library of 4 professionally-engineered prompt chains + an interactive runner.
Human/AI-agnostic (works with ChatGPT, Claude, GLM, local models — no API keys,
no maintenance liability). Chains map 1:1 to observed paid categories:

- `research_synthesis` — topic → cited synthesis report (€345 category)
- `content_pipeline` — idea → publish-ready content (€420 category)
- `spec_to_code` — spec → tested code w/ adversarial review (€540 category)
- `self_refining` — artifact → scored critique/refine loop (€210 category)

```bash
python promptflow.py list                 # browse
python promptflow.py run spec_to_code spec="build a CSV deduplicator" language=Python
python promptflow.py export research_synthesis   # export as .md files to resell
```

---

## Suggested listings (copy-paste ready)

### Listing A — "I'll build a custom web scraper for any website" (€50–€150)
> Zero-dependency Python scraper — no installs, runs anywhere. Links, emails,
> images, or any custom data pattern (prices, SKUs, phone numbers). Polite
> crawling (robots.txt, rate limiting). Delivery: the tool + your site's
> configuration + JSON/CSV output. Basic: 1 page, 1 pattern (€50). Standard:
> full-site crawl up to 3 levels (€90). Premium: custom multi-pattern + dedupe
> + scheduled-run setup (€150).

### Listing B — "Python file & folder automation script" (€85)
> Batch-organize any folder by type or date, bulk-rename files with custom
> patterns, find duplicate files by content, generate folder inventory
> reports. Standard library only — nothing to install. Safe by design:
> preview-everything mode before anything moves (€85, 2-day delivery).

### Listing C — "Professional AI prompt chain system" (€150–€250)
> 4 engineered multi-step prompt workflows (research synthesis, content
> pipeline, spec-to-code, self-refining loop) with an interactive runner
> that carries each step's output into the next. Model-agnostic — works with
> ChatGPT, Claude, GLM, or local models; no API keys, yours forever. Exported
> as ready-to-use files + runner (€150 base, +€50 per custom chain built for
> your specific workflow).

**Where to list:** PeoplePerHour (prices above validated there), Fiverr,
Contra. Listing takes ~10 minutes each.

## Test log (2026-09-08)

- `scrapekit.py`: links from example.com ✅, multi-page crawl of
  quotes.toscrape.com (4 pages, 49 deduped results, JSON output) ✅, visible
  text extraction ✅, syntax clean under `-W error::SyntaxWarning` ✅
- `fileforge.py`: organize dry-run + apply (5 files → 3 category folders) ✅,
  content-hash dedupe (found planted duplicate) ✅, pattern rename dry-run ✅,
  CSV inventory report ✅
- `promptflow.py`: chain listing ✅, spec printing ✅, `.md` export ✅,
  interactive run with variable substitution and step-to-step output
  chaining (piped test through all 4 steps) ✅
- `leadminer.py`: syntax clean ✅, live run against real sites (title
  extraction, clean CSV output, true-negative behavior on contactless
  sites) ✅, extractor unit tests (US + international phone formats, mailto
  emails, junk-address filtering: noreply/footer/abuse, LinkedIn social
  detection) ✅
- `apiforge.py`: syntax clean ✅, live paginated pull from GitHub API
  (2 pages, 6 rows, nested-key flattened CSV) ✅, rows-path extraction
  against JSONPlaceholder (200 rows) ✅, monitor mode against live API
  (OK-state tracking, correct exit code 2 on expect-mismatch) ✅, sync
  incremental mode (200 rows stored, zero duplicates across cycles,
  unique-ID verification) ✅
- `reportforge.py`: syntax clean ✅, 300-row synthetic sales dataset →
  full report with KPI cards, stats tables, SVG histogram/bar charts,
  group-by segment tables (11KB self-contained HTML) ✅, edge cases:
  categorical-only data ✅, sparse data ✅, single row ✅ (no crashes)
- `csvkit.py`: syntax clean ✅, merge with mismatched column orders and
  extra columns (column union, 4 rows aligned) ✅, merge --dedupe (1
  duplicate removed) ✅, clean (whitespace trim, N/A normalization, email
  case fix all verified) ✅, pivot with duplicate-key summing (2026-01
  North 100+20=120) ✅, compare (1 added, 1 changed detected with status
  CSV) ✅
- `mediasift.py`: syntax clean ✅, real-header parsing verified against
  synthetic PNGs and JPEGs (5 images, correct w/h/format/orientation/
  aspect) ✅, organize-by-aspect dry-run (panorama/landscape/portrait/
  square routing) ✅, rename with {date}/{n}/{wxh} patterns ✅, CSV
  inventory ✅, resize command sheet generation ✅
- `sitedoctor.py`: syntax clean ✅, live audit of quotes.toscrape.com
  (6 pages crawled, missing-description and duplicate-title correctly
  detected on real HTML, 4KB HTML report) ✅, detector unit tests on
  crafted pages (unreachable/404, long title, missing description,
  multiple H1s, image missing alt, mixed content, orphan) — all fire
  correctly ✅
- `mailforge.py`: syntax clean ✅, .eml mode (3 drafts, parse-back round-
  trip with correct To/Subject personalization) ✅, review.html sheet ✅,
  suspicious-address warning (noreply@test.com flagged) ✅, hard error on
  unknown {placeholder} with column list in the message ✅
- `taskloop.py`: syntax clean ✅, live run loop (echo job, 4 logged
  cycles, JSONL with exit/duration) ✅, failure mode (exit 3 logged with
  retry r0→r1 and backoff) ✅, cron matcher: 12/12 patterns (exact,
  wildcard, steps, ranges, lists, day-of-week) ✅, Windows Task Scheduler
  XML generation ✅, stale-lock handling ✅

## Legal/ethical notes for listings

- ScrapeKit: sold for legitimate data collection (public data, research,
  price monitoring). Include "buyer responsible for compliance with target
  site's terms" in the listing — standard practice for scraping gigs.
- No malware-adjacent anything: no persistence, no obfuscation, no network
  tricks — it's a plain urllib client with rate limiting.
