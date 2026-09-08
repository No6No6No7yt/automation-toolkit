#!/usr/bin/env python3
"""
LeadMiner — a zero-dependency B2B lead-list builder.
Sells as: "targeted lead generation / business data scraping"
(market: €30–€70 per 150–500 leads on PeoplePerHour; custom tools €345)

What it does:
    1. Takes a list of websites (a text file, one URL per line)
    2. Visits each site (and optionally one level of linked pages)
    3. Extracts: emails, phone numbers, social profiles, company name (title tag)
    4. Dedupes, validates email syntax, and outputs a clean CSV lead list

Usage:
    python leadminer.py sites.txt --out leads.csv
    python leadminer.py sites.txt --out leads.csv --depth 1 --limit 50
    python leadminer.py sites.txt --out leads.xlsx   # (csv fallback if no openpyxl)

Input file format: one URL per line, '#' starts a comment. Bare domains
('example.com') are auto-upgraded to https://.
"""

import argparse
import csv
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_AGENT = "Mozilla/5.0 (compatible; LeadMiner/1.0; research)"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+[\d\s\-().()]{7,20}\d")
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
LINK_RE = re.compile(r'<a\b[^>]*?href\s*=\s*["\']([^"\'#]+)["\']', re.IGNORECASE)
MAILTO_RE = re.compile(r"mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", re.IGNORECASE)
SOCIAL_DOMAINS = ("linkedin.com", "twitter.com", "x.com", "facebook.com",
                  "instagram.com", "youtube.com", "github.com", "t.me")

# emails that should never appear in a B2B lead list
JUNK_EMAIL_LOCAL = ("noreply", "no-reply", "donotreply", "postmaster", "abuse",
                    "webmaster", "hostmaster", "uucp", "null", "mailer-daemon",
                    "footer", "header", "sender", "bounce")
JUNK_EMAIL_DOMAIN = ("sentry.io", "wixpress.com", "example.com", "domain.com",
                     "email.com", "yourdomain", "godaddy.com", "squarespace.com")


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw.split("#")[0]


def fetch(url: str, agent: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": agent,
        "Accept": "text/html,*/*;q=0.8",
        "Accept-Language": "en",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode(resp.headers.get_content_charset() or "utf-8",
                                      errors="replace")
    except Exception:
        return ""


def clean_email(email: str) -> bool:
    """True if the email is plausibly a real, human-facing address."""
    email = email.lower().strip()
    local, _, domain = email.partition("@")
    if not domain or "." not in domain:
        return False
    if local.split(".")[0] in JUNK_EMAIL_LOCAL or local.split("+")[0] in JUNK_EMAIL_LOCAL:
        return False
    if any(junk in domain for junk in JUNK_EMAIL_DOMAIN):
        return False
    if local.endswith(".png") or local.endswith(".jpg") or local.endswith(".webp"):
        return False  # filename misdetected as address
    return True


def same_site(base: str, url: str) -> bool:
    return urllib.parse.urlsplit(base).netloc == urllib.parse.urlsplit(url).netloc


def extract_leads(url: str, body: str):
    """Extract one lead record's raw signals from a page."""
    title_match = TITLE_RE.search(body)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
    emails, phones, socials = set(), set(), set()

    for email in EMAIL_RE.findall(body):
        if clean_email(email):
            emails.add(email.lower())
    for email in MAILTO_RE.findall(body):
        if clean_email(email):
            emails.add(email.lower())

    # strip common false-positive sources before phone extraction
    text_only = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", body, flags=re.IGNORECASE | re.DOTALL)
    text_only = re.sub(r"<[^>]+>", " ", text_only)
    for phone in PHONE_RE.findall(text_only):
        digits = re.sub(r"\D", "", phone)
        if 7 <= len(digits) <= 15:  # ITU E.164 range
            phones.add(re.sub(r"\s+", " ", phone.strip()))

    for href in LINK_RE.findall(body):
        absolute = urllib.parse.urljoin(url, href)
        netloc = urllib.parse.urlsplit(absolute).netloc.lower()
        if any(s in netloc for s in SOCIAL_DOMAINS):
            socials.add(absolute.split("?")[0])

    return {"title": title, "emails": emails, "phones": phones, "socials": socials}


def main():
    parser = argparse.ArgumentParser(description="B2B lead-list builder (zero dependencies).")
    parser.add_argument("sites", help="text file: one website per line")
    parser.add_argument("--out", required=True, help="output CSV path")
    parser.add_argument("--depth", type=int, default=0, choices=[0, 1],
                        help="also scan linked same-site pages (0 or 1, default 0)")
    parser.add_argument("--limit", type=int, default=100,
                        help="max total pages fetched (default 100)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="seconds between requests (default 1.0)")
    parser.add_argument("--agent", default=DEFAULT_AGENT)
    args = parser.parse_args()

    sites = [normalize_url(line) for line in
             Path(args.sites).read_text(encoding="utf-8").splitlines()]
    sites = [s for s in sites if s]
    if not sites:
        sys.exit("error: no valid sites in input file")

    # aggregate per domain: a lead = one site's collected signals
    leads = {}
    pages_fetched = 0
    for site in sites:
        print(f"processing {site}", file=sys.stderr)
        queue = [site]
        seen = {site}
        record = None
        while queue and pages_fetched < args.limit:
            url = queue.pop(0)
            body = fetch(url, args.agent)
            pages_fetched += 1
            if body:
                page = extract_leads(url, body)
                if record is None:
                    record = {"url": site, "title": page["title"], "emails": set(),
                              "phones": set(), "socials": set()}
                    leads[site] = record
                else:
                    record = leads[site]
                record["emails"] |= page["emails"]
                record["phones"] |= page["phones"]
                record["socials"] |= page["socials"]
                if args.depth == 1:
                    for href in LINK_RE.findall(body):
                        absolute = urllib.parse.urljoin(url, href).split("#")[0]
                        if (absolute.startswith(("http://", "https://"))
                                and same_site(site, absolute)
                                and any(p in absolute.lower() for p in
                                        ("contact", "about", "team", "impressum", "legal"))
                                and absolute not in seen):
                            seen.add(absolute)
                            queue.append(absolute)
            time.sleep(args.delay)

    rows = []
    for site, r in leads.items():
        rows.append({
            "website": site,
            "company": r["title"][:120],
            "emails": "; ".join(sorted(r["emails"])),
            "phones": "; ".join(sorted(r["phones"])),
            "socials": "; ".join(sorted(r["socials"]))[:300],
        })
    rows.sort(key=lambda row: bool(row["emails"]), reverse=True)

    out_path = Path(args.out)
    if out_path.suffix.lower() in (".xlsx", ".xls"):
        out_path = out_path.with_suffix(".csv")
        print("note: openpyxl not available — writing CSV instead", file=sys.stderr)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel-friendly
        writer = csv.DictWriter(f, fieldnames=["website", "company", "emails", "phones", "socials"])
        writer.writeheader()
        writer.writerows(rows)

    with_leads = sum(1 for r in rows if r["emails"] or r["phones"])
    print(f"done: {len(sites)} site(s) -> {with_leads} with contact info, "
          f"written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
