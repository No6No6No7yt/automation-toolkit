#!/usr/bin/env python3
r"""
ScrapeKit — a zero-dependency, configurable web scraper.
Sells as: "custom data extraction from any website" (market: €35–€345 on PeoplePerHour)

Usage:
    python scrapekit.py <url> [--select PATTERN]... [--links] [--emails] [--images]
                         [--depth N] [--out FILE] [--format json|csv|txt]
                         [--limit N] [--delay SECONDS] [--agent UA]

Design notes:
- Standard library only: no pip install, works on any Python 3.9+
- Polite by default: 1s delay between requests, custom User-Agent, robots.txt respected
- Extraction modes: full text, links, email addresses, images, or custom regex patterns
- Same-domain crawling with configurable depth
- Clean JSON/CSV/text output

Examples:
    # All emails from a site, 2 levels deep
    python scrapekit.py https://example.com --emails --depth 2 --out emails.json

    # All links on one page
    python scrapekit.py https://example.com --links --out links.csv

    # Custom regex (e.g. phone numbers) on a single page
    python scrapekit.py https://example.com --select "\+\d[\d\s\-()]{7,}\d" --out phones.txt
"""

import argparse
import csv
import html
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser

DEFAULT_AGENT = "ScrapeKit/1.0 (+polite research scraper; contact: seller sets this)"
DEFAULT_DELAY = 1.0

TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
LINK_RE = re.compile(r'<a\b[^>]*?href\s*=\s*["\']([^"\'#]+)["\']', re.IGNORECASE)
IMG_RE = re.compile(r'<img\b[^>]*?src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


class ScrapeError(Exception):
    pass


def fetch(url: str, agent: str, timeout: int = 15) -> str:
    """Fetch a URL and return the decoded body."""
    req = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        raise ScrapeError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise ScrapeError(f"Cannot reach {url}: {e.reason}") from e


def visible_text(page_html: str) -> str:
    """Extract readable text from HTML, dropping scripts/styles/tags."""
    text = SCRIPT_STYLE_RE.sub(" ", page_html)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize(base: str, href: str) -> str:
    """Resolve href against base and return absolute http(s) URL."""
    href = href.strip()
    if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return ""
    absolute = urllib.parse.urljoin(base, href)
    if not absolute.startswith(("http://", "https://")):
        return ""
    return absolute.split("#")[0]


class Scraper:
    def __init__(self, start_url: str, agent: str, delay: float, respect_robots: bool = True):
        self.start = start_url
        self.agent = agent
        self.delay = delay
        self.domain = urllib.parse.urlsplit(start_url).netloc
        self.robots = None
        if respect_robots:
            robots_url = urllib.parse.urljoin(start_url, "/robots.txt")
            self.robots = urllib.robotparser.RobotFileParser()
            try:
                self.robots.set_url(robots_url)
                self.robots.read()
            except Exception:
                self.robots = None  # unreachable robots.txt -> crawl allowed

    def allowed(self, url: str) -> bool:
        if self.robots is None:
            return True
        return self.robots.can_fetch(self.agent, url)

    def same_site(self, url: str) -> bool:
        return urllib.parse.urlsplit(url).netloc == self.domain

    def crawl(self, depth: int, limit: int):
        """Yield (url, body_html) for pages up to `depth` links from start."""
        visited, queue, seen = set(), [(self.start, 0)], {self.start}
        count = 0
        while queue:
            url, level = queue.pop(0)
            if url in visited or not self.allowed(url):
                continue
            visited.add(url)
            try:
                body = fetch(url, self.agent)
            except ScrapeError as e:
                print(f"skip: {e}", file=sys.stderr)
                time.sleep(self.delay)
                continue
            count += 1
            yield url, body
            if count >= limit:
                return
            if level < depth:
                for href in LINK_RE.findall(body):
                    absolute = normalize(url, href)
                    if absolute and self.same_site(absolute) and absolute not in seen:
                        seen.add(absolute)
                        queue.append((absolute, level + 1))
            time.sleep(self.delay)


def extract(kind: str, url: str, body: str, patterns):
    """Return list of {url, match} dicts for the requested extraction kind."""
    found = []
    if kind == "text":
        found.append({"url": url, "text": visible_text(body)})
    elif kind == "links":
        for href in LINK_RE.findall(body):
            absolute = normalize(url, href)
            if absolute:
                found.append({"url": url, "match": absolute})
    elif kind == "emails":
        for email in sorted(set(EMAIL_RE.findall(visible_text(body)))):
            found.append({"url": url, "match": email})
    elif kind == "images":
        for src in IMG_RE.findall(body):
            absolute = normalize(url, src)
            if absolute:
                found.append({"url": url, "match": absolute})
    elif kind == "custom":
        for pattern in patterns:
            for m in re.findall(pattern, body):
                value = m if isinstance(m, str) else " ".join(m)
                found.append({"url": url, "match": html.unescape(value)})
    return found


def dedupe(records):
    """Drop exact duplicate matches across pages, keeping first-seen order."""
    seen, out = set(), []
    for r in records:
        key = r.get("match", r.get("text", ""))[:500]
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def write_out(records, out_path: str, fmt: str):
    if fmt == "json":
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
    elif fmt == "csv":
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for r in records:
                writer.writerow([r["url"], r.get("match", r.get("text", ""))])
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(r.get("match", r.get("text", "")) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Polite, zero-dependency web scraper (ScrapeKit)."
    )
    parser.add_argument("url", help="start URL, e.g. https://example.com")
    kind = parser.add_mutually_exclusive_group(required=True)
    kind.add_argument("--select", metavar="REGEX", action="append", default=[],
                     help="custom regex pattern (repeatable)")
    kind.add_argument("--links", action="store_true", help="extract all links")
    kind.add_argument("--emails", action="store_true", help="extract email addresses")
    kind.add_argument("--images", action="store_true", help="extract image URLs")
    kind.add_argument("--text", action="store_true", help="extract visible page text")
    parser.add_argument("--depth", type=int, default=0,
                        help="follow same-site links up to this depth (default: single page)")
    parser.add_argument("--limit", type=int, default=25,
                        help="max pages to fetch (default: 25)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                        help=f"seconds between requests (default: {DEFAULT_DELAY})")
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="User-Agent string")
    parser.add_argument("--no-robots", action="store_true", help="ignore robots.txt (not recommended)")
    parser.add_argument("--out", default=None, help="output file (default: print to console)")
    parser.add_argument("--format", choices=["json", "csv", "txt"], default="json",
                        help="output format (default: json)")
    args = parser.parse_args()

    if args.select:
        kind_name, patterns = "custom", args.select
    elif args.links:
        kind_name, patterns = "links", []
    elif args.emails:
        kind_name, patterns = "emails", []
    elif args.images:
        kind_name, patterns = "images", []
    else:
        kind_name, patterns = "text", []

    scraper = Scraper(args.url, args.agent, args.delay, respect_robots=not args.no_robots)
    records = []
    for page_url, body in scraper.crawl(args.depth, args.limit):
        records.extend(extract(kind_name, page_url, body, patterns))
        print(f"fetched: {page_url}", file=sys.stderr)

    records = dedupe(records)
    if not records:
        print("No results found.", file=sys.stderr)
        return 1

    if args.out:
        write_out(records, args.out, args.format)
        print(f"{len(records)} results -> {args.out}", file=sys.stderr)
    else:
        for r in records:
            value = r.get("match", r.get("text", ""))
            print(f"{r['url']}\t{value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
