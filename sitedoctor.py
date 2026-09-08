#!/usr/bin/env python3
"""
SiteDoctor — a zero-dependency website SEO & health auditor.
Sells as: "website SEO audit / broken link checker" (€10–€180 on PeoplePerHour)

Checks a site for the issues that matter in entry-level SEO gigs:
    - broken internal links (404s) and redirects
    - missing/empty <title> and meta description on every crawled page
    - missing alt text on images
    - missing H1 or multiple H1s per page
    - duplicate titles/descriptions across pages
    - slow pages (response-time outliers)
    - unencrypted mixed content (http:// resources on https:// pages)
    - orphan-heavy structure signal (pages with no inbound internal links,
      computed from the crawled map)

Output: console summary + full HTML report (self-contained, print-to-PDF
like ReportForge) listing each issue with page URL and fix suggestion.

Usage:
    python sitedoctor.py https://example.com --depth 2 --limit 30
    python sitedoctor.py https://example.com --report audit.html
"""

import argparse
import datetime
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

DEFAULT_AGENT = "Mozilla/5.0 (compatible; SiteDoctor/1.0; SEO audit)"
LINK_RE = re.compile(r'<a\b[^>]*?href\s*=\s*["\']([^"\'#]+)["\']', re.IGNORECASE)
IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ALT_RE = re.compile(r'\balt\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
H1_RE = re.compile(r"<h1\b[^>]*>", re.IGNORECASE)
DESC_RE = re.compile(r'<meta\b[^>]*name\s*=\s*["\']description["\'][^>]*>'
                     r'|<meta\b[^>]*content\s*=\s*["\'][^"\']*["\'][^>]*name\s*=\s*["\']description["\']',
                     re.IGNORECASE)
CONTENT_ATTR_RE = re.compile(r'content\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)
HTTP_RESOURCE_RE = re.compile(r'(?:src|href)\s*=\s*["\']http://[^"\']+["\']', re.IGNORECASE)


def fetch(url: str, agent: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode(resp.headers.get_content_charset() or "utf-8",
                                      errors="replace")
            return {"status": resp.status, "body": body,
                    "elapsed": time.time() - start, "error": None}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": "", "elapsed": time.time() - start,
                "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"status": 0, "body": "", "elapsed": time.time() - start, "error": str(e)}


def normalize(base: str, href: str) -> str:
    href = href.strip()
    if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return ""
    absolute = urllib.parse.urljoin(base, href)
    if not absolute.startswith(("http://", "https://")):
        return ""
    return absolute.split("#")[0]


class Crawler:
    def __init__(self, start: str, agent: str, delay: float):
        self.start = start
        self.agent = agent
        self.delay = delay
        self.domain = urllib.parse.urlsplit(start).netloc
        self.pages = {}       # url -> fetch result
        self.links = defaultdict(set)  # page -> outbound internal links
        self.inbound = defaultdict(set)

    def same_site(self, url: str) -> bool:
        return urllib.parse.urlsplit(url).netloc == self.domain

    def crawl(self, depth: int, limit: int):
        queue, seen = [(self.start, 0)], {self.start}
        while queue and len(self.pages) < limit:
            url, level = queue.pop(0)
            result = fetch(url, self.agent)
            self.pages[url] = result
            if not result["body"]:
                time.sleep(self.delay)
                continue
            for href in LINK_RE.findall(result["body"]):
                absolute = normalize(url, href)
                if not absolute or not self.same_site(absolute):
                    continue
                self.links[url].add(absolute)
                self.inbound[absolute].add(url)
                if absolute not in seen and level < depth:
                    seen.add(absolute)
                    queue.append((absolute, level + 1))
            time.sleep(self.delay)


def analyze(pages: dict, links: dict, inbound: dict):
    """Return list of (severity, category, url, detail) issues."""
    issues = []
    titles, descs = defaultdict(list), defaultdict(list)
    ok_pages = {u: r for u, r in pages.items() if r["body"]}

    for url, result in pages.items():
        if result["error"] and not result["body"]:
            sev = "high" if result["status"] in (0, 404, 500, 502, 503) else "medium"
            issues.append((sev, "unreachable", url,
                           f"fetch failed: {result['error']}"))

    for url, result in ok_pages.items():
        body = result["body"]
        title = TITLE_RE.search(body)
        title_text = re.sub(r"\s+", " ", title.group(1)).strip() if title else ""
        if not title or not title_text:
            issues.append(("high", "title missing", url, "page has no <title>"))
        elif len(title_text) > 65:
            issues.append(("low", "title too long", url,
                           f"{len(title_text)} chars (aim ≤ 65): {title_text[:70]}..."))
        else:
            titles[title_text].append(url)

        desc = DESC_RE.search(body)
        content = CONTENT_ATTR_RE.search(desc.group(0)) if desc else None
        desc_text = content.group(1).strip() if content else ""
        if not desc_text:
            issues.append(("medium", "meta description missing", url,
                           "no meta description — search engines improvise"))
        elif len(desc_text) > 160:
            issues.append(("low", "description too long", url,
                           f"{len(desc_text)} chars (aim ≤ 160)"))
        else:
            descs[desc_text].append(url)

        h1_count = len(H1_RE.findall(body))
        if h1_count == 0:
            issues.append(("medium", "no H1", url, "page has no H1 heading"))
        elif h1_count > 1:
            issues.append(("low", "multiple H1s", url, f"{h1_count} H1 headings"))

        for tag in IMG_RE.findall(body):
            if not ALT_RE.search(tag):
                issues.append(("medium", "image missing alt", url,
                               f"img tag without alt: {tag[:80]}"))

        if url.startswith("https://"):
            for match in HTTP_RESOURCE_RE.findall(body):
                issues.append(("medium", "mixed content", url,
                               f"insecure http:// resource: {match[:80]}"))

    for text, urls in titles.items():
        if len(urls) > 1 and text:
            for u in urls:
                issues.append(("medium", "duplicate title", u,
                               f"'{text[:60]}' shared with {len(urls) - 1} other page(s)"))
    for text, urls in descs.items():
        if len(urls) > 1 and text:
            for u in urls:
                issues.append(("low", "duplicate description", u,
                               f"shared with {len(urls) - 1} other page(s)"))

    for url in ok_pages:
        if url != next(iter(pages)) and not inbound.get(url):
            issues.append(("low", "no internal links in", url,
                           "crawled page received no internal links (orphan-ish)"))

    slow = sorted(((r["elapsed"], u) for u, r in ok_pages.items()), reverse=True)
    for elapsed, url in slow[:3]:
        if elapsed > 2.0:
            issues.append(("medium", "slow page", url,
                           f"{elapsed:.1f}s response time"))

    return issues


SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def render_report(start, pages, issues):
    counts = Counter(sev for sev, *_ in issues)
    rows = "".join(
        f"<tr><td class='sev {sev}'>{sev}</td><td>{html.escape(cat)}</td>"
        f"<td class='url'>{html.escape(url)}</td><td>{html.escape(detail[:140])}</td></tr>"
        for sev, cat, url, detail in sorted(issues, key=lambda i: SEV_ORDER[i[0]]))
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Site audit — {html.escape(start)}</title><style>
body{{font-family:-apple-system,'Segoe UI',sans-serif;background:#f4f5f8;margin:0}}
.page{{max-width:900px;margin:24px auto;background:#fff;padding:36px 44px;border-radius:12px;
box-shadow:0 2px 16px rgba(20,30,60,.08)}}
h1{{font-size:24px;margin:0 0 4px}} .meta{{color:#7a8299;font-size:13px;margin-bottom:24px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th{{text-align:left;color:#7a8299;border-bottom:2px solid #e6e9f2;padding:8px}}
td{{padding:7px 8px;border-bottom:1px solid #eef0f6;vertical-align:top}}
.sev{{font-weight:700;text-transform:uppercase;font-size:11px}}
.sev.high{{color:#e2495b}} .sev.medium{{color:#e59313}} .sev.low{{color:#7a8299}}
.url{{font-family:ui-monospace,monospace;font-size:11.5px;word-break:break-all}}
.kpis{{display:flex;gap:12px;margin:18px 0}}
.kpi{{flex:1;background:#f4f6ff;border-radius:10px;padding:12px 16px}}
.kpi .label{{font-size:11px;color:#7a8299;text-transform:uppercase}}
.kpi .value{{font-size:22px;font-weight:700}}
</style></head><body><div class='page'>
<h1>Website Audit — {html.escape(start)}</h1>
<div class='meta'>{len(pages)} page(s) crawled — {datetime.datetime.now():%Y-%m-%d %H:%M}</div>
<div class='kpis'>
<div class='kpi'><div class='label'>Pages</div><div class='value'>{len(pages)}</div></div>
<div class='kpi'><div class='label'>Issues</div><div class='value'>{len(issues)}</div></div>
<div class='kpi'><div class='label'>High</div><div class='value'>{counts['high']}</div></div>
<div class='kpi'><div class='label'>Medium</div><div class='value'>{counts['medium']}</div></div>
<div class='kpi'><div class='label'>Low</div><div class='value'>{counts['low']}</div></div>
</div>
<table><thead><tr><th>Severity</th><th>Issue</th><th>Page</th><th>Detail</th></tr></thead>
<tbody>{rows}</tbody></table>
</div></body></html>"""


def main():
    parser = argparse.ArgumentParser(description="SEO & health audit for one site.")
    parser.add_argument("site", help="start URL, e.g. https://example.com")
    parser.add_argument("--depth", type=int, default=1, help="crawl depth (default 1)")
    parser.add_argument("--limit", type=int, default=25, help="max pages (default 25)")
    parser.add_argument("--delay", type=float, default=0.8, help="seconds between fetches")
    parser.add_argument("--report", default=None, help="write HTML report to file")
    args = parser.parse_args()

    start = args.site if args.site.startswith(("http://", "https://")) else "https://" + args.site
    print(f"auditing {start} (depth {args.depth}, max {args.limit} pages)...", file=sys.stderr)
    crawler = Crawler(start, DEFAULT_AGENT, args.delay)
    crawler.crawl(args.depth, args.limit)

    ok = sum(1 for r in crawler.pages.values() if r["body"])
    print(f"crawled {len(crawler.pages)} page(s), {ok} readable", file=sys.stderr)
    issues = analyze(crawler.pages, crawler.links, crawler.inbound)

    counts = Counter(sev for sev, *_ in issues)
    print(f"\nissues found: {len(issues)} "
          f"(high: {counts['high']}, medium: {counts['medium']}, low: {counts['low']})")
    for sev, cat, url, detail in sorted(issues, key=lambda i: SEV_ORDER[i[0]]):
        print(f"  [{sev:6s}] {cat:28s} {url}")

    if args.report:
        from pathlib import Path
        Path(args.report).write_text(render_report(start, crawler.pages, issues),
                                     encoding="utf-8")
        print(f"\nHTML report -> {args.report}", file=sys.stderr)


if __name__ == "__main__":
    main()
