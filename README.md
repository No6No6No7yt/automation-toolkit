# The 12-Tool Automation Toolkit

Twelve single-file Python tools that do the work people pay for — scraping,
file wrangling, lead lists, insight reports, SEO audits, mail merges,
scheduled jobs. Each one runs on plain Python 3.9+ with **zero
dependencies** (standard library only), previews every change before it
happens, and has been tested end-to-end.

**Try the live demo with real sample outputs:**
https://no6no6no7yt.github.io/automation-toolkit/demos/index.html

**Download:** [v1.0.0 release](https://github.com/No6No6No7yt/automation-toolkit/releases/tag/v1.0.0)

---

## The tools

| Tool | What it does | One-liner |
|------|--------------|-----------|
| **ScrapeKit** `scrapekit.py` | Web scraping: links, emails, images, or any custom regex pattern; polite same-site crawling; JSON/CSV output | `python scrapekit.py https://example.com --emails --depth 2` |
| **FileForge** `fileforge.py` | Organize/rename/dedupe files, folder inventories — dry-run by default, never deletes | `python fileforge.py organize ~/Downloads --by category --apply` |
| **PromptFlow** `promptflow.py` | 4 engineered AI prompt chains + interactive runner; model-agnostic, no API keys | `python promptflow.py run spec_to_code spec="build X" language=Python` |
| **LeadMiner** `leadminer.py` | B2B contact extraction from websites: emails, phones, socials, junk-filtered | `python leadminer.py sites.txt --out leads.csv --depth 1` |
| **APIForge** `apiforge.py` | REST API pulls (paginated), incremental sync with dedupe, endpoint monitoring | `python apiforge.py sync https://api/x --id-field id --every 900` |
| **ReportForge** `reportforge.py` | CSV → styled insight report: KPIs, stats, SVG charts, segments, print-to-PDF | `python reportforge.py sales.csv --group-by region --out r.html` |
| **CSVKit** `csvkit.py` | Merge/dedupe/clean/pivot/compare CSVs — Excel-friendly | `python csvkit.py merge a.csv b.csv --out all.csv --dedupe` |
| **MediaSift** `mediasift.py` | Image dimensions from raw bytes, bulk rename/organize, inventory CSV | `python mediasift.py organize ~/photos --by aspect --apply` |
| **SiteDoctor** `sitedoctor.py` | SEO/health audit: broken links, titles, meta, H1s, alt text, mixed content | `python sitedoctor.py https://site.com --report audit.html` |
| **FaqForge** `faqforge.py` | Q&A text → styled FAQ page + schema.org markup + CSV | `python faqforge.py faq.txt --title "FAQ" --outdir out/` |
| **MailForge** `mailforge.py` | Mail merge to .eml drafts / review sheet — never sends, hard-fails on missing fields | `python mailforge.py tpl.txt rcv.csv --eml --out drafts/` |
| **TaskLoop** `taskloop.py` | Scheduled jobs: interval or cron, JSONL logs, retries, autostart configs | `python taskloop.py run "python job.py" --cron "0 9 * * 1-5"` |

## Design rules (why these tools exist)

1. **Zero dependencies, forever.** Standard library only. `pip install`
   is a support burden and a supply-chain risk; there is none here.
2. **Nothing happens without a preview.** Every mutating tool is dry-run
   until you pass `--apply`. Nothing deletes blindly.
3. **One file per tool.** Copy the one you need, run it, done. The
   toolkit zip is 64 KB total.
4. **Polite by default.** Scrapers rate-limit and respect robots.txt;
   LeadMiner/MailForge filter junk addresses and refuse to fire off
   half-personalized mail.
5. **Tested, with receipts.** Every tool has an end-to-end test log in
   this README — run against live sites, synthetic fixtures, and edge
   cases.

## Test log (all passing, 2026-09-08)

<details>
<summary>Full test evidence — expand</summary>

- **scrapekit.py** — live crawl of quotes.toscrape.com (4 pages, 49
  deduped results), regex extraction, JSON/CSV/TXT output, robots.txt
  respected
- **fileforge.py** — organize by category on synthetic tree (5 files →
  3 folders), content-hash dedupe found planted duplicate, pattern
  rename, CSV inventory
- **promptflow.py** — all 4 chains: variable substitution, step-to-step
  output chaining, .md export
- **leadminer.py** — extractor unit tests (US/international phone
  formats, mailto parsing, noreply/footer/abuse junk filtering, LinkedIn
  detection); live run true-negative on contactless sites
- **apiforge.py** — live paginated pull from GitHub API, incremental
  sync with 200 rows / zero duplicates across cycles, monitor with
  correct exit codes on expect-mismatch
- **reportforge.py** — 300-row dataset → full report (KPIs, SVG
  histogram, group-by segments); edge cases: categorical-only, sparse,
  single-row
- **csvkit.py** — merge with mismatched columns, dedupe, clean
  (whitespace/N-A normalization/email case), pivot with duplicate-key
  summing, compare (added/removed/changed)
- **mediasift.py** — real JPEG/PNG header parsing from bytes (SOF/IHDR
  markers), aspect routing, {date}/{n}/{wxh} renames, resize command
  sheet
- **sitedoctor.py** — live audit of quotes.toscrape.com; unit tests:
  all 7 detector types fire on crafted bad pages
- **faqforge.py** — multi-line answer joining, orphan-question warning,
  valid JSON-LD schema round-trip parse
- **mailforge.py** — .eml round-trip parse with personalization,
  suspicious-address warning, hard error on unknown placeholder
- **taskloop.py** — live run loop (4 logged cycles), failure+retry
  logging with backoff, 12/12 cron matcher patterns, Windows Task
  Scheduler XML generation

</details>

## For freelancers

Each tool maps to a proven paid-service category (scraping, data
cleaning, lead gen, SEO audits, report writing, automation). SELL.md
contains the listing copy, price tiers, and fulfillment workflow.

## Regenerate the demo site

```bash
python demosite.py   # rebuilds demos/index.html with fresh sample outputs
python bundle.py    # rebuilds toolkit.zip with sha256
```

## License

MIT — do whatever, just don't blame me.
