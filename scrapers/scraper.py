"""
Multi-Platform Job Scraper
Scrapes all 20 ATS platforms for AI/GenAI remote jobs.
"""

import re
import time
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urlencode, quote_plus

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser

logger = logging.getLogger("scraper")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ─── Seen-jobs dedup cache (in-memory + file) ───────────────
_seen: set = set()

def _job_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()

def _is_seen(url: str) -> bool:
    h = _job_hash(url)
    return h in _seen

def _mark_seen(url: str):
    _seen.add(_job_hash(url))


# ─── Recency filter ─────────────────────────────────────────
def _posted_recently(text: str, within_hours: int = 24) -> bool:
    """Return True if text suggests job was posted within X hours."""
    if not text:
        return True  # unknown = allow
    text = text.lower()
    patterns = [
        (r"(\d+)\s*min", lambda m: int(m.group(1)) / 60),
        (r"(\d+)\s*hour", lambda m: int(m.group(1))),
        (r"just now|today|moments ago", lambda m: 0),
        (r"(\d+)\s*day", lambda m: int(m.group(1)) * 24),
    ]
    for pat, fn in patterns:
        m = re.search(pat, text)
        if m:
            try:
                hours_ago = fn(m)
                return hours_ago <= within_hours
            except:
                pass
    return True  # can't determine, include


# ─── Base Scraper ────────────────────────────────────────────
class BaseScraper:
    def __init__(self, platform: dict, roles: List[str], filters: dict):
        self.platform = platform
        self.roles    = roles
        self.filters  = filters
        self.session  = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self) -> List[Dict]:
        raise NotImplementedError

    def _filter_job(self, job: Dict) -> bool:
        title   = (job.get("title") or "").lower()
        desc    = (job.get("description") or "").lower()
        full    = title + " " + desc

        # Remote check
        if self.filters.get("remote_only"):
            if not any(kw in full for kw in ["remote","work from home","wfh","distributed"]):
                if "remote" not in (job.get("location") or "").lower():
                    return False

        # Exclude keywords
        for kw in self.filters.get("exclude_keywords", []):
            if kw in full:
                return False

        # Recency
        if not _posted_recently(
            job.get("posted_at", ""),
            self.filters.get("posted_within_hours", 24)
        ):
            return False

        return True

    def _make_job(self, **kwargs) -> Dict:
        return {
            "title":       kwargs.get("title", ""),
            "company":     kwargs.get("company", ""),
            "location":    kwargs.get("location", "Remote"),
            "url":         kwargs.get("url", ""),
            "description": kwargs.get("description", ""),
            "posted_at":   kwargs.get("posted_at", ""),
            "platform":    self.platform["name"],
            "salary":      kwargs.get("salary", ""),
        }


# ─── Greenhouse Scraper ──────────────────────────────────────
class GreenhouseScraper(BaseScraper):
    """
    Greenhouse boards expose a JSON API at:
    https://boards.greenhouse.io/{company}/jobs.json
    We search across known AI companies + aggregate boards.
    """
    # Top companies likely hiring AI engineers on Greenhouse
    COMPANIES = [
        "anthropic","openai","cohere","mistralai","huggingface",
        "scale","labelbox","weights-biases","modal","replicate",
        "together","fireworks","anyscale","verta","snorkelai",
        "clarifai","deepmind","inflection","characterai","adept",
        "mosaic","mosaicml","databricks","snowflake","pinecone",
        "weaviate","chroma","qdrant","zilliz","mindsdb",
    ]

    def search(self) -> List[Dict]:
        jobs = []
        for company in self.COMPANIES:
            try:
                url = f"{self.platform['base']}/{company}/jobs.json"
                resp = self.session.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for j in data.get("jobs", []):
                    title = j.get("title", "")
                    if not any(
                        kw.lower() in title.lower()
                        for kw in ["ai","ml","machine learning","llm","genai","gen ai","engineer"]
                    ):
                        continue
                    apply_url = j.get("absolute_url", "")
                    if _is_seen(apply_url):
                        continue
                    job = self._make_job(
                        title=title,
                        company=company.replace("-", " ").title(),
                        url=apply_url,
                        location=j.get("location", {}).get("name", ""),
                        posted_at=j.get("updated_at", ""),
                    )
                    if self._filter_job(job):
                        _mark_seen(apply_url)
                        jobs.append(job)
            except Exception as e:
                logger.debug(f"Greenhouse {company}: {e}")
        logger.info(f"Greenhouse: found {len(jobs)} jobs")
        return jobs


# ─── Ashby HQ Scraper ───────────────────────────────────────
class AshbyScraper(BaseScraper):
    COMPANIES = [
        "linear","vercel","loom","notion","figma","retool","brex",
        "ramp","rippling","gusto","lattice","glean","perplexity",
        "elevenlabs","runway","pika","midjourney","learnlm",
    ]

    def search(self) -> List[Dict]:
        jobs = []
        for company in self.COMPANIES:
            try:
                url  = f"https://jobs.ashbyhq.com/{company}"
                resp = self.session.get(url, timeout=10)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href  = a["href"]
                    title = a.get_text(strip=True)
                    if not href.startswith("/"):
                        continue
                    if not any(kw.lower() in title.lower() for kw in
                               ["ai","ml","engineer","llm","machine learning"]):
                        continue
                    full_url = f"https://jobs.ashbyhq.com{href}"
                    if _is_seen(full_url):
                        continue
                    job = self._make_job(
                        title=title, company=company.title(),
                        url=full_url, location="Remote"
                    )
                    if self._filter_job(job):
                        _mark_seen(full_url)
                        jobs.append(job)
            except Exception as e:
                logger.debug(f"Ashby {company}: {e}")
        logger.info(f"Ashby: found {len(jobs)} jobs")
        return jobs


# ─── Workable Scraper ────────────────────────────────────────
class WorkableScraper(BaseScraper):
    def search(self) -> List[Dict]:
        jobs = []
        for role in self.roles[:3]:  # rate-limit friendly
            try:
                url = f"https://apply.workable.com/api/v1/widget/jobs"
                params = {"query": role, "location": "remote"}
                resp = self.session.get(url, params=params, timeout=12)
                if resp.status_code != 200:
                    continue
                for j in resp.json().get("results", []):
                    apply_url = j.get("url", "")
                    if _is_seen(apply_url):
                        continue
                    job = self._make_job(
                        title=j.get("title", ""),
                        company=j.get("company", {}).get("name", ""),
                        url=apply_url,
                        location=j.get("location", ""),
                        posted_at=j.get("published_on", ""),
                    )
                    if self._filter_job(job):
                        _mark_seen(apply_url)
                        jobs.append(job)
            except Exception as e:
                logger.debug(f"Workable {role}: {e}")
        logger.info(f"Workable: found {len(jobs)} jobs")
        return jobs


# ─── SurelyRemote Scraper ────────────────────────────────────
class SurelyRemoteScraper(BaseScraper):
    """Uses Melanie's existing subscription (logged-in session)."""

    def search(self) -> List[Dict]:
        jobs = []
        try:
            # SurelyRemote has a search endpoint
            for role in self.roles:
                encoded = quote_plus(role)
                url = f"https://surelyremote.com/jobs?q={encoded}&type=full-time"
                resp = self.session.get(url, timeout=15)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                # Parse job cards (selectors may need adjustment)
                for card in soup.select(".job-card, .job-listing, article.job"):
                    title_el   = card.select_one("h2, h3, .job-title, .title")
                    company_el = card.select_one(".company, .company-name")
                    link_el    = card.select_one("a[href]")
                    posted_el  = card.select_one(".posted, .date, time")

                    if not title_el:
                        continue
                    title      = title_el.get_text(strip=True)
                    company    = company_el.get_text(strip=True) if company_el else ""
                    href       = link_el["href"] if link_el else ""
                    apply_url  = href if href.startswith("http") else f"https://surelyremote.com{href}"
                    posted_at  = posted_el.get_text(strip=True) if posted_el else ""

                    if _is_seen(apply_url):
                        continue
                    job = self._make_job(
                        title=title, company=company,
                        url=apply_url, posted_at=posted_at,
                        location="Remote"
                    )
                    if self._filter_job(job):
                        _mark_seen(apply_url)
                        jobs.append(job)
                time.sleep(1)
        except Exception as e:
            logger.error(f"SurelyRemote error: {e}")
        logger.info(f"SurelyRemote: found {len(jobs)} jobs")
        return jobs


# ─── Generic ATS Scraper (Playwright) ───────────────────────
class GenericATSScraper(BaseScraper):
    """
    Browser-based scraper for ATS platforms that require JS rendering.
    Covers: Jobvite, Taleo, SuccessFactors, Oracle, Rippling, ADP, etc.
    """

    def search(self) -> List[Dict]:
        jobs = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for role in self.roles[:2]:
                try:
                    jobs.extend(self._scrape_platform(browser, role))
                except Exception as e:
                    logger.debug(f"Generic ATS {self.platform['name']} {role}: {e}")
            browser.close()
        return jobs

    def _scrape_platform(self, browser: Browser, role: str) -> List[Dict]:
        jobs   = []
        base   = self.platform["base"]
        page   = browser.new_page()
        page.set_extra_http_headers(HEADERS)

        search_url = f"{base}?q={quote_plus(role)}&location=remote"
        page.goto(search_url, timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Try common job listing selectors
        selectors = [
            "a[data-job-id]", ".job-title a", "a.job-link",
            "[class*='job'] a[href]", "h3 a", "h2 a",
        ]
        links = []
        for sel in selectors:
            try:
                links = page.query_selector_all(sel)
                if links:
                    break
            except:
                pass

        for link in links[:20]:
            try:
                title = link.inner_text().strip()
                href  = link.get_attribute("href") or ""
                if not title or not href:
                    continue
                full_url = href if href.startswith("http") else f"{base}{href}"
                if _is_seen(full_url):
                    continue
                job = self._make_job(
                    title=title,
                    company=self.platform["name"],
                    url=full_url,
                    location="Remote",
                )
                if self._filter_job(job):
                    _mark_seen(full_url)
                    jobs.append(job)
            except:
                pass

        page.close()
        return jobs


# ─── Scraper Factory ─────────────────────────────────────────
SCRAPER_MAP = {
    "greenhouse":   GreenhouseScraper,
    "ashby":        AshbyScraper,
    "workable":     WorkableScraper,
    "surelyremote": SurelyRemoteScraper,
    # all others get generic browser scraper
}

def get_scraper(platform: dict, roles: List[str], filters: dict) -> BaseScraper:
    cls = SCRAPER_MAP.get(platform["type"], GenericATSScraper)
    return cls(platform, roles, filters)


def scrape_all_platforms(
    platforms: List[dict],
    roles: List[str],
    filters: dict,
) -> List[Dict]:
    """Run all scrapers and return deduplicated job list."""
    all_jobs = []
    for platform in platforms:
        try:
            scraper = get_scraper(platform, roles, filters)
            jobs    = scraper.search()
            all_jobs.extend(jobs)
            logger.info(f"  [{platform['name']}] → {len(jobs)} jobs")
        except Exception as e:
            logger.error(f"  [{platform['name']}] FAILED: {e}")
        time.sleep(0.5)

    logger.info(f"Total jobs found this scan: {len(all_jobs)}")
    return all_jobs
