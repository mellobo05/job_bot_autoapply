#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║   Daily GenAI Job Alert — Melanie Lobo                      ║
║   Target: Senior GenAI/LLM/RAG · India-Remote · ₹35L+       ║
╠══════════════════════════════════════════════════════════════╣
║  SOURCES (all FREE):                                         ║
║  1. Greenhouse API    — 18 hand-picked AI companies          ║
║  2. Remotive API      — filtered for India/APAC/Worldwide    ║
║  3. Jobicy API        — remote jobs with timezone tags       ║
║  4. Himalayas API     — remote-first, India-friendly         ║
║  5. We Work Remotely  — RSS, India-open roles                ║
║  6. RemoteOK API      — worldwide remote tech jobs           ║
╠══════════════════════════════════════════════════════════════╣
║  KEY CHANGE: Only shows roles open to India-based workers    ║
║  Filters OUT "US only", "EU only", "Americas only" etc.      ║
╠══════════════════════════════════════════════════════════════╣
║  INSTALL:  pip install requests schedule pytz                ║
║  TEST:     python genai_job_alert.py --once                  ║
║  SCHEDULE: python genai_job_alert.py  (stays running 9AM)   ║
╚══════════════════════════════════════════════════════════════╝
"""

import requests
import smtplib
import schedule
import time
import argparse
import logging
import xml.etree.ElementTree as ET
import pytz
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from collections import Counter

# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════

SENDER_EMAIL       = "melanieharriet05@gmail.com"
RECIPIENT_EMAIL    = "melanieharriet05@gmail.com"

# HOW TO GET GMAIL APP PASSWORD:
# 1. https://myaccount.google.com/apppasswords
# 2. Create → name "Job Alert" → copy 16-char password
# 3. Paste below WITHOUT spaces
GMAIL_APP_PASSWORD = "jwmd nojb qusn ajii"

IST          = pytz.timezone("Asia/Kolkata")
HOURS_WINDOW = 48   # look back 48h to handle API lag

# ══════════════════════════════════════════════════════════════
#  GREENHOUSE TARGET COMPANIES
# ══════════════════════════════════════════════════════════════

GREENHOUSE_COMPANIES = {
    "trmlabs":     "TRM Labs",
    "natera":      "Natera",
    "censys":      "Censys",
    "affinity":    "Affinity",
    "gleanwork":   "Glean",
    "snorkelai":   "Snorkel AI",
    "samsara":     "Samsara",
    "doordashusa": "DoorDash",
    "cohere":      "Cohere",
    "scaleai":     "Scale AI",
    "openai":      "OpenAI",
    "anthropic":   "Anthropic",
    "hightouch":   "Hightouch",
    "brightai":    "Bright AI",
    "gr8tech":     "GR8 Tech",
    "further":     "Further",
    "figma":       "Figma",
    "notion":      "Notion",
}

# ══════════════════════════════════════════════════════════════
#  FILTER KEYWORDS
# ══════════════════════════════════════════════════════════════

AI_KEYWORDS = [
    "ai engineer", "genai", "gen ai", "llm", "ml engineer",
    "machine learning engineer", "nlp engineer", "rag",
    "applied ai", "artificial intelligence engineer",
    "generative ai", "language model", "ai platform",
    "ai backend", "ai infrastructure", "vector db",
    "ai agent", "llm orchestration", "foundation model",
    "ai/ml", "ml platform", "mlops", "large language",
]

SENIORITY_KEYWORDS = [
    "senior", "staff", "lead", "principal", "architect",
    "sr.", "sr ", " iv", "head of",
]

EXCLUDE_TITLE_KEYWORDS = [
    "sales", "marketing", "recruiter", "finance", "legal",
    "ux designer", "product manager", "operations", "accountant",
    "coordinator", "phlebotomist", "clinical", "lab scientist",
    "data reviewer", "oncology", "pathologist", "office manager",
    "customer success", "business development", "content writer",
]

# ══════════════════════════════════════════════════════════════
#  INDIA-REMOTE LOCATION LOGIC  ← KEY CHANGE
# ══════════════════════════════════════════════════════════════

# Locations that are GOOD for India-based workers
INDIA_OK_SIGNALS = [
    "india", "worldwide", "world wide", "global", "anywhere",
    "apac", "asia", "asia pacific", "remote",
    "international", "work from home", "wfh",
    "all countries", "any country", "no restriction",
]

# Locations that EXCLUDE India (skip these roles)
INDIA_EXCLUDE_SIGNALS = [
    "us only", "usa only", "united states only",
    "uk only", "eu only", "europe only",
    "americas only", "north america only",
    "canada only", "australia only",
    "must be located in us", "must reside in",
    "us-based", "us based", "us citizens",
    "must be authorized to work in the us",
    "latin america", "latam only",
    "eastern european", "eastern europe only",
    # Specific non-India office cities (not remote-to-India)
    "new york, ny", "san francisco, ca", "seattle, wa",
    "austin, tx", "chicago, il", "boston, ma",
    "london, uk", "berlin, germany", "toronto, canada",
    "singapore", "dubai", "amsterdam",
]

def is_india_friendly(location: str, description: str = "") -> bool:
    """
    Returns True if the role is open to India-based remote workers.
    Logic:
    - If location/desc explicitly excludes India (US only, EU only etc.) → False
    - If location says India, Worldwide, APAC, Global, Remote → True
    - If location is empty/unknown → True (include, can't tell)
    """
    loc  = location.lower().strip()
    desc = description.lower()

    # Hard exclude — explicitly not India-friendly
    for signal in INDIA_EXCLUDE_SIGNALS:
        if signal in loc or signal in desc:
            return False

    # If location is empty — could be anywhere, include it
    if not loc:
        return True

    # Explicitly India-OK signals
    for signal in INDIA_OK_SIGNALS:
        if signal in loc or signal in desc:
            return True

    # If location has no geo signals at all — include (benefit of doubt)
    return True


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def now_ist() -> datetime:
    return datetime.now(IST)


def parse_dt(raw: str):
    if not raw:
        return None
    raw = raw.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(raw[:26], fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except Exception:
            pass
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(raw)
    except Exception:
        pass
    return None


def is_recent(raw_date: str) -> bool:
    dt = parse_dt(raw_date)
    if dt is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS_WINDOW)
    return dt >= cutoff


def is_ai_role(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in AI_KEYWORDS)


def is_senior(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in SENIORITY_KEYWORDS)


def is_excluded_title(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in EXCLUDE_TITLE_KEYWORDS)


def is_relevant(title: str, location: str = "", description: str = "") -> bool:
    return (
        not is_excluded_title(title)
        and is_ai_role(title)
        and is_senior(title)
        and is_india_friendly(location, description)
    )


def time_ago(raw_date: str) -> str:
    dt = parse_dt(raw_date)
    if not dt:
        return "Recently posted"
    hours = int((datetime.now(timezone.utc) - dt).total_seconds() / 3600)
    if hours < 1:
        return "Just posted"
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


# ══════════════════════════════════════════════════════════════
#  SOURCE 1 — GREENHOUSE (18 companies, free API)
# ══════════════════════════════════════════════════════════════

def fetch_greenhouse() -> list[dict]:
    results = []
    log.info("  [Greenhouse] scraping 18 companies...")
    for slug, name in GREENHOUSE_COMPANIES.items():
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            matched = 0
            for j in r.json().get("jobs", []):
                title    = j.get("title", "")
                date_raw = j.get("updated_at") or j.get("created_at", "")
                loc_obj  = j.get("location", {})
                location = loc_obj.get("name", "") if isinstance(loc_obj, dict) else str(loc_obj)
                if not is_recent(date_raw):
                    continue
                if not is_relevant(title, location):
                    continue
                results.append({
                    "source":   "Greenhouse",
                    "company":  name,
                    "title":    title,
                    "location": location or "Remote",
                    "url":      j.get("absolute_url", f"https://job-boards.greenhouse.io/{slug}"),
                    "date_raw": date_raw,
                    "tags":     [],
                })
                matched += 1
            if matched:
                log.info(f"    ✅ {name}: {matched} match(es)")
        except Exception as e:
            log.warning(f"    ⚠ {slug}: {e}")
    log.info(f"  [Greenhouse] → {len(results)} matches")
    return results


# ══════════════════════════════════════════════════════════════
#  SOURCE 2 — REMOTIVE (free API, filter India-friendly)
# ══════════════════════════════════════════════════════════════

def fetch_remotive() -> list[dict]:
    results = []
    log.info("  [Remotive] fetching jobs...")
    urls = [
        "https://remotive.com/api/remote-jobs?category=software-dev&limit=200",
        "https://remotive.com/api/remote-jobs?category=data&limit=100",
    ]
    seen = set()
    for url in urls:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            for j in r.json().get("jobs", []):
                jid      = j.get("id", "")
                if jid in seen:
                    continue
                seen.add(jid)
                title    = j.get("title", "")
                date_raw = j.get("publication_date", "")
                company  = j.get("company_name", "")
                location = j.get("candidate_required_location", "")
                apply_url = j.get("url", "")
                desc     = j.get("description", "")[:500]

                if not is_recent(date_raw):
                    continue
                if not is_relevant(title, location, desc):
                    continue
                results.append({
                    "source":   "Remotive",
                    "company":  company,
                    "title":    title,
                    "location": location or "Worldwide Remote",
                    "url":      apply_url,
                    "date_raw": date_raw,
                    "tags":     j.get("tags", [])[:4],
                })
        except Exception as e:
            log.warning(f"  [Remotive] error: {e}")
    log.info(f"  [Remotive] → {len(results)} matches")
    return results


# ══════════════════════════════════════════════════════════════
#  SOURCE 3 — JOBICY (free API, has timezone filter)
# ══════════════════════════════════════════════════════════════

def fetch_jobicy() -> list[dict]:
    results = []
    log.info("  [Jobicy] fetching jobs...")
    try:
        r = requests.get(
            "https://jobicy.com/api/v2/remote-jobs?count=50&tag=ai,machine-learning,llm",
            timeout=15,
        )
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            title    = j.get("jobTitle", "")
            date_raw = j.get("pubDate", "")
            company  = j.get("companyName", "")
            location = j.get("jobGeo", "")
            tz_tag   = j.get("jobIndustry", "")
            apply_url = j.get("url", "")
            desc     = j.get("jobExcerpt", "")

            # jobGeo "Anywhere" = worldwide including India
            region_ok = location.lower() in ("anywhere", "worldwide", "global", "") \
                        or "india" in location.lower() \
                        or "apac" in location.lower() \
                        or "asia" in location.lower()
            if not region_ok:
                continue
            if not is_recent(date_raw):
                continue
            if not is_relevant(title, location, desc):
                continue
            results.append({
                "source":   "Jobicy",
                "company":  company,
                "title":    title,
                "location": location or "Anywhere",
                "url":      apply_url,
                "date_raw": date_raw,
                "tags":     [],
            })
    except Exception as e:
        log.warning(f"  [Jobicy] error: {e}")
    log.info(f"  [Jobicy] → {len(results)} matches")
    return results


# ══════════════════════════════════════════════════════════════
#  SOURCE 4 — HIMALAYAS (free API, remote-first)
# ══════════════════════════════════════════════════════════════

def fetch_himalayas() -> list[dict]:
    results = []
    log.info("  [Himalayas] fetching jobs...")
    searches = ["ai engineer", "llm engineer", "machine learning", "genai"]
    seen = set()
    for query in searches:
        try:
            r = requests.get(
                f"https://himalayas.app/jobs/api?q={requests.utils.quote(query)}&limit=50",
                timeout=15,
            )
            r.raise_for_status()
            for j in r.json().get("jobs", []):
                jid      = j.get("slug", j.get("id", ""))
                if jid in seen:
                    continue
                seen.add(jid)
                title    = j.get("title", "")
                date_raw = j.get("createdAt", "")
                company  = j.get("company", {}).get("name", "") if isinstance(j.get("company"), dict) else ""
                # Himalayas has countryRestrictions field
                restrictions = j.get("countryRestrictions", [])
                # Empty restrictions = open to all including India
                # If restrictions exist and India not in them → skip
                if restrictions:
                    restricted_lower = [r.lower() for r in restrictions]
                    india_ok = any(
                        x in restricted_lower
                        for x in ["india", "apac", "asia", "anywhere", "worldwide"]
                    )
                    if not india_ok:
                        continue
                apply_url = j.get("applicationUrl") or f"https://himalayas.app/jobs/{jid}"
                if not is_recent(date_raw):
                    continue
                if not is_relevant(title, "remote"):
                    continue
                results.append({
                    "source":   "Himalayas",
                    "company":  company,
                    "title":    title,
                    "location": "Remote (India OK)" if not restrictions else ", ".join(restrictions[:3]),
                    "url":      apply_url,
                    "date_raw": date_raw,
                    "tags":     j.get("tags", [])[:4],
                })
        except Exception as e:
            log.warning(f"  [Himalayas] error for '{query}': {e}")
    log.info(f"  [Himalayas] → {len(results)} matches")
    return results


# ══════════════════════════════════════════════════════════════
#  SOURCE 5 — WE WORK REMOTELY (RSS)
# ══════════════════════════════════════════════════════════════

def fetch_weworkremotely() -> list[dict]:
    results = []
    log.info("  [WeWorkRemotely] fetching RSS...")
    feeds = [
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    ]
    seen = set()
    for feed_url in feeds:
        try:
            r = requests.get(feed_url, timeout=15)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            for item in root.iter("item"):
                title_raw  = (item.find("title") or type("",(),{"text":""})()).text or ""
                url        = (item.find("link")   or type("",(),{"text":""})()).text or ""
                date_raw   = (item.find("pubDate") or type("",(),{"text":""})()).text or ""
                region_el  = item.find("{https://weworkremotely.com}region")
                region     = region_el.text if region_el is not None else ""

                if url in seen:
                    continue
                seen.add(url)

                # Parse "Company: Title" format
                if ":" in title_raw:
                    company, job_title = title_raw.split(":", 1)
                    company, job_title = company.strip(), job_title.strip()
                else:
                    company, job_title = "", title_raw

                # WWR region check
                region_lower = region.lower()
                if region_lower and not any(
                    s in region_lower for s in [
                        "worldwide", "anywhere", "india", "apac", "asia",
                        "global", "remote", ""
                    ]
                ):
                    # Has a region restriction — check it's not excluding India
                    if any(x in region_lower for x in ["usa", "us only", "europe", "uk only", "latam"]):
                        continue

                if not is_recent(date_raw):
                    continue
                if not is_relevant(job_title, region):
                    continue
                results.append({
                    "source":   "WeWorkRemotely",
                    "company":  company,
                    "title":    job_title,
                    "location": region or "Worldwide Remote",
                    "url":      url,
                    "date_raw": date_raw,
                    "tags":     [],
                })
        except Exception as e:
            log.warning(f"  [WeWorkRemotely] error: {e}")
    log.info(f"  [WeWorkRemotely] → {len(results)} matches")
    return results


# ══════════════════════════════════════════════════════════════
#  SOURCE 6 — REMOTEOK (free public API)
# ══════════════════════════════════════════════════════════════

def fetch_remoteok() -> list[dict]:
    results = []
    log.info("  [RemoteOK] fetching jobs...")
    try:
        r = requests.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "GenAI-Job-Alert/1.0"},
            timeout=15,
        )
        r.raise_for_status()
        for j in r.json()[1:]:   # skip legal notice at index 0
            title    = j.get("position", "")
            date_raw = j.get("date", "")
            company  = j.get("company", "")
            tags     = j.get("tags", [])
            apply_url = j.get("url", f"https://remoteok.com/l/{j.get('id','')}")
            location = j.get("location", "") or "Remote"

            # RemoteOK location can say "No US" or region restrictions
            if not is_india_friendly(location):
                continue
            if not is_recent(date_raw):
                continue
            if not is_relevant(title, "remote"):
                continue
            results.append({
                "source":   "RemoteOK",
                "company":  company,
                "title":    title,
                "location": "Worldwide Remote",
                "url":      apply_url,
                "date_raw": date_raw,
                "tags":     tags[:4] if tags else [],
            })
    except Exception as e:
        log.warning(f"  [RemoteOK] error: {e}")
    log.info(f"  [RemoteOK] → {len(results)} matches")
    return results


# ══════════════════════════════════════════════════════════════
#  AGGREGATOR
# ══════════════════════════════════════════════════════════════

def scrape_all() -> list[dict]:
    ist_now = now_ist().strftime("%d %b %Y %I:%M %p IST")
    log.info("=" * 60)
    log.info(f"GenAI Job Alert — {ist_now}")
    log.info(f"Window: {HOURS_WINDOW}h | Filter: India-remote | Sources: 6")
    log.info("=" * 60)

    all_jobs = []
    all_jobs += fetch_greenhouse()
    all_jobs += fetch_remotive()
    all_jobs += fetch_jobicy()
    all_jobs += fetch_himalayas()
    all_jobs += fetch_weworkremotely()
    all_jobs += fetch_remoteok()

    # Deduplicate by title + company
    seen, unique = set(), []
    for j in all_jobs:
        key = (j["title"].lower().strip(), j["company"].lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(j)

    # Sort newest first
    unique.sort(
        key=lambda j: parse_dt(j["date_raw"]) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    log.info(f"\n{'='*60}")
    log.info(f"✅ Total India-remote GenAI Senior matches: {len(unique)}")
    log.info(f"{'='*60}\n")
    return unique


# ══════════════════════════════════════════════════════════════
#  EMAIL
# ══════════════════════════════════════════════════════════════

SOURCE_COLORS = {
    "Greenhouse":     "#059669",
    "Remotive":       "#0284c7",
    "Jobicy":         "#7c3aed",
    "Himalayas":      "#0891b2",
    "WeWorkRemotely": "#d97706",
    "RemoteOK":       "#db2777",
}


def build_email(jobs: list[dict]) -> str:
    ist_now   = now_ist()
    today_str = ist_now.strftime("%A, %B %d %Y · %I:%M %p IST")
    count     = len(jobs)
    source_counts = Counter(j["source"] for j in jobs)

    source_pills = " &nbsp;·&nbsp; ".join(
        '<span style="color:{};font-weight:600;">{} ({})</span>'.format(
            SOURCE_COLORS.get(s, "#6b7280"), s, c
        )
        for s, c in source_counts.items()
    )

    if count == 0:
        body = f"""
        <div style="text-align:center;padding:48px 20px;">
          <div style="font-size:44px;margin-bottom:16px;">🔍</div>
          <p style="font-size:17px;font-weight:700;color:#374151;margin:0 0 10px;">
            No new India-friendly GenAI roles in the last 48 hours
          </p>
          <p style="font-size:14px;color:#6b7280;margin:0;">
            Checked all 6 sources — nothing new today matching your filters.<br>
            Check back tomorrow at 9 AM IST!
          </p>
        </div>
        """
    else:
        cards = ""
        for j in jobs:
            title   = j["title"]
            company = j["company"] or "—"
            source  = j["source"]
            loc     = j["location"] or "Remote"
            url     = j["url"]
            posted  = time_ago(j["date_raw"])
            tags    = j.get("tags", [])
            color   = SOURCE_COLORS.get(source, "#6b7280")

            tags_html = "".join(
                f'<span style="font-size:11px;background:#f3f4f6;color:#374151;'
                f'padding:2px 8px;border-radius:20px;margin-right:4px;">{t}</span>'
                for t in tags[:4]
            )

            # India-friendly badge
            loc_lower = loc.lower()
            if "india" in loc_lower:
                loc_badge = f'🇮🇳 {loc}'
                badge_bg  = "#fef3c7"
                badge_col = "#92400e"
            elif any(x in loc_lower for x in ["worldwide", "anywhere", "global"]):
                loc_badge = f'🌍 {loc}'
                badge_bg  = "#ecfdf5"
                badge_col = "#065f46"
            elif "apac" in loc_lower or "asia" in loc_lower:
                loc_badge = f'🌏 {loc}'
                badge_bg  = "#eff6ff"
                badge_col = "#1e40af"
            else:
                loc_badge = f'🌐 {loc}'
                badge_bg  = "#f3f4f6"
                badge_col = "#374151"

            cards += f"""
            <div style="background:#fff;border:1px solid #e5e7eb;
                        border-left:4px solid {color};border-radius:10px;
                        padding:18px 20px;margin-bottom:12px;">
              <div style="display:flex;justify-content:space-between;
                          align-items:flex-start;flex-wrap:wrap;gap:8px;">
                <div style="flex:1;min-width:0;">
                  <p style="margin:0 0 4px;font-size:15px;font-weight:700;color:#111827;">
                    {title}
                  </p>
                  <p style="margin:0;font-size:13px;color:#6b7280;">
                    🏢 <strong style="color:#374151;">{company}</strong>
                    &nbsp;·&nbsp;
                    <span style="background:{color}22;color:{color};font-size:11px;
                                 padding:2px 8px;border-radius:12px;font-weight:600;">
                      {source}
                    </span>
                  </p>
                </div>
                <span style="background:{badge_bg};color:{badge_col};font-size:12px;
                             padding:4px 10px;border-radius:20px;font-weight:600;
                             white-space:nowrap;flex-shrink:0;">
                  {loc_badge}
                </span>
              </div>
              {f'<div style="margin-top:8px;">{tags_html}</div>' if tags_html else ''}
              <div style="margin-top:12px;display:flex;justify-content:space-between;
                          align-items:center;flex-wrap:wrap;gap:8px;">
                <div>
                  <span style="font-size:12px;color:#9ca3af;">🕐 {posted}</span>
                  &nbsp;
                  <span style="font-size:11px;background:#fef3c7;color:#92400e;
                               padding:2px 8px;border-radius:12px;font-weight:600;">
                    🇮🇳 India-Remote OK
                  </span>
                </div>
                <a href="{url}"
                   style="background:#2563eb;color:#fff;font-size:13px;font-weight:600;
                          padding:7px 18px;border-radius:7px;text-decoration:none;">
                  Apply →
                </a>
              </div>
            </div>
            """
        body = cards

    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f1f5f9;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:660px;margin:28px auto;padding:0 14px 48px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1e3a8a 0%,#6d28d9 100%);
              border-radius:14px;padding:28px 26px 22px;margin-bottom:14px;color:#fff;">
    <p style="margin:0 0 3px;font-size:11px;letter-spacing:1.5px;
              text-transform:uppercase;opacity:0.7;">Daily Job Alert · Melanie Lobo</p>
    <h1 style="margin:0 0 4px;font-size:23px;font-weight:800;">
      🤖 GenAI Senior Roles — India Remote
    </h1>
    <p style="margin:0 0 14px;font-size:12px;opacity:0.75;">{today_str}</p>
    <div style="display:inline-block;background:rgba(255,255,255,0.18);
                border-radius:24px;padding:5px 16px;font-size:14px;font-weight:700;">
      {count} India-friendly match{'es' if count != 1 else ''} · last 48 hrs
    </div>
  </div>

  <!-- Source breakdown -->
  <div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
              padding:11px 16px;margin-bottom:10px;font-size:12px;">
    <strong style="color:#374151;">Sources:</strong> &nbsp; {source_pills if source_pills else "—"}
  </div>

  <!-- Filters -->
  <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:10px;
              padding:11px 16px;margin-bottom:16px;font-size:12px;color:#92400e;">
    <strong>🇮🇳 India-Remote Filter ON:</strong> &nbsp;
    Excludes "US only / EU only / Americas only" &nbsp;·&nbsp;
    Keeps "Worldwide / APAC / India / Anywhere" &nbsp;·&nbsp;
    Senior · GenAI/LLM/RAG · ₹35L+ target
  </div>

  {body}

  <!-- Footer -->
  <div style="text-align:center;margin-top:24px;padding-top:18px;
              border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;">
    <p style="margin:0 0 2px;">
      Greenhouse · Remotive · Jobicy · Himalayas · WeWorkRemotely · RemoteOK
    </p>
    <p style="margin:0 0 2px;">All free public APIs — no scraper credits needed</p>
    <p style="margin:0;">Auto-sent at 9:00 AM IST · Melanie's Daily GenAI Job Alert 🇮🇳</p>
  </div>

</div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════
#  SEND EMAIL
# ══════════════════════════════════════════════════════════════

def send_email(html: str, count: int):
    ist_date = now_ist().strftime("%b %d, %Y")
    subject  = f"🤖🇮🇳 {count} India-Remote GenAI role{'s' if count!=1 else ''} · {ist_date}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            s.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        log.info(f"✅ Email sent → {RECIPIENT_EMAIL}  [{count} India-remote jobs]")
    except smtplib.SMTPAuthenticationError:
        log.error("❌ Gmail auth failed.")
        log.error("   Fix: https://myaccount.google.com/apppasswords")
        log.error("   Create app password → paste in GMAIL_APP_PASSWORD (no spaces)")
    except Exception as e:
        log.error(f"❌ Email error: {e}")


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def run():
    jobs = scrape_all()
    html = build_email(jobs)
    send_email(html, len(jobs))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true",
                        help="Run once immediately (for Task Scheduler / cron)")
    args = parser.parse_args()

    if args.once:
        run()
    else:
        log.info("Scheduler active. Fires daily at 09:00 AM IST (03:30 UTC).")
        log.info("Running once now. Ctrl+C to stop.\n")
        run()
        schedule.every().day.at("03:30").do(run)   # 03:30 UTC = 09:00 IST
        while True:
            schedule.run_pending()
            time.sleep(30)


# ══════════════════════════════════════════════════════════════
#  WINDOWS TASK SCHEDULER SETUP (Cursor users)
# ══════════════════════════════════════════════════════════════
#
#  Step 1 — Find your Python path (run in Cursor terminal):
#      where python
#
#  Step 2 — Create scheduled task (paste in Cursor terminal):
#      schtasks /create /tn "GenAI Job Alert"
#        /tr "C:\path\to\python.exe C:\Users\lobomela\.cursor\JOB\job_bot_autoapply\genai_job_alert.py --once"
#        /sc daily /st 09:00 /f
#
#  Step 3 — Test it right now:
#      schtasks /run /tn "GenAI Job Alert"
#
#  Step 4 — Check your inbox for the email!
#
# ══════════════════════════════════════════════════════════════