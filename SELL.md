# How to sell this toolkit (step-by-step)

## 1. Where to list
- **PeoplePerHour** — prices below are validated against this market
- **Fiverr** — same gigs, slightly lower prices, higher volume
- **Contra** — commission-free, good for the higher tiers

## 2. Your public assets (already live)
- Repo: https://github.com/No6No6No7yt/automation-toolkit
- Live demo: https://no6no6no7yt.github.io/automation-toolkit/demos/index.html
- Download: https://github.com/No6No6No7yt/automation-toolkit/releases/tag/v1.0.0

The demo site is the gig gallery: screenshot it for gig images, or link it
directly (Fiverr allows external portfolio links on profile).

## 3. The seven listings to create (copy from README.md)

| Gig | Price | Delivery time |
|-----|-------|---------------|
| Custom web scraper for any website | $50/$90/$150 | 2 days |
| Data cleaning / merge spreadsheets / dedupe | $20/$40/$60 | 1 day |
| CSV → branded insight report with charts | $30/$60/$120 | 2 days |
| Website SEO audit with HTML report | $30/$80/$180 | 3 days |
| B2B lead list from any websites | $30/$70/$150 | 2 days |
| FAQ page with schema markup | $60/$120 | 2 days |
| Scheduled automation (no Zapier fees) | $45/$90/$115 | 2 days |

## 4. Order fulfillment workflow
1. Buyer sends input (CSV / URL / site list / Q&A text)
2. Run the matching tool (all commands in README.md)
3. Deliver the output file + toolkit.zip if they want to self-serve
4. For recurring jobs: sell a TaskLoop setup (run it on their machine or
   yours — logs prove every run)

## 5. Positioning lines that work
- "Zero dependencies — nothing to install, works on any computer"
- "Every action is previewed before it runs — nothing is deleted blindly"
- "Full run logs on every scheduled job — you can audit everything"
- "You own the tool — no subscription, no monthly fees"

## 8. ScriptSentry — Roblox Studio plugin (separate product line)

**Where it sells:** Roblox Creator Marketplace (plugins, priced in USD).
**File:** `roblox-plugin/ScriptSentry.server.lua` — analysis-only code
quality scanner (deprecated globals, executor-only API, silent pcall,
giant scripts), dockable panel, click-to-jump. 12/12 rule tests pass in
real Lua; full-file syntax validated.

**Steps to list (needs Roblox account, ~15 min):**
1. creator.roblox.com → Creation → Plugins
2. Upload as .rbxm (right-click the script in Studio → Save as plugin)
3. Category: Developer Tools · Price: $4.99 equivalent
4. Description: paste from `roblox-plugin/README.md`

**Why it can sell:** code-quality plugins are rare on the marketplace
(vs. asset generators). Roblox devs have real money and real pain with
legacy scripts full of deprecated globals.
