"""
LinkedIn Networking Bot
Finds hiring managers / recruiters for applied-to companies
and sends personalized connection requests.
"""

import logging
import time
import random
from datetime import date
from pathlib import Path
import json
from typing import Optional, Dict, List

from playwright.sync_api import sync_playwright, Browser, Page

logger = logging.getLogger("linkedin")

# Track daily connection count
_DAILY_FILE = "data/linkedin_daily.json"


def _get_today_count() -> int:
    try:
        data = json.loads(Path(_DAILY_FILE).read_text())
        if data.get("date") == str(date.today()):
            return data.get("count", 0)
    except:
        pass
    return 0


def _increment_count():
    count = _get_today_count() + 1
    Path(_DAILY_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(_DAILY_FILE).write_text(json.dumps({"date": str(date.today()), "count": count}))


class LinkedInBot:
    def __init__(self, config: dict):
        self.config   = config
        self.email    = config["email"]
        self.password = config["password"]
        self.max_day  = config.get("max_connects_day", 20)
        self.template = config.get("message_template", "")
        self._browser = None
        self._page    = None
        self._logged_in = False

    def _login(self, page: Page) -> bool:
        """Log in to LinkedIn."""
        try:
            page.goto("https://www.linkedin.com/login", timeout=20000)
            page.fill("#username", self.email)
            page.fill("#password", self.password)
            page.click("button[type='submit']")
            page.wait_for_timeout(3000)

            if "feed" in page.url or "mynetwork" in page.url:
                logger.info("LinkedIn: logged in successfully")
                return True
            logger.warning("LinkedIn login may have failed — check credentials or 2FA")
            return False
        except Exception as e:
            logger.error(f"LinkedIn login error: {e}")
            return False

    def find_and_connect(
        self,
        company: str,
        role: str,
        job_url: str,
    ) -> Optional[Dict]:
        """
        Search for recruiter / hiring manager at company
        and send a connection request.

        Returns: {"name": ..., "title": ..., "profile_url": ...} or None
        """
        if not self.config.get("enabled"):
            return None
        if not self.password:
            logger.warning("LinkedIn password not set — skipping outreach")
            return None
        if _get_today_count() >= self.max_day:
            logger.info("LinkedIn daily limit reached — will resume tomorrow")
            return None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page    = browser.new_page()

            if not self._login(page):
                browser.close()
                return None

            result = self._search_and_connect(page, company, role, job_url)
            browser.close()
            return result

    def _search_and_connect(
        self, page: Page, company: str, role: str, job_url: str
    ) -> Optional[Dict]:
        """Search for recruiter at company and connect."""
        try:
            # Search for recruiter/talent HR at company
            search_queries = [
                f'recruiter "{company}"',
                f'talent acquisition "{company}"',
                f'hiring manager "{company}" engineer',
            ]

            for query in search_queries:
                from urllib.parse import quote_plus
                search_url = (
                    f"https://www.linkedin.com/search/results/people/"
                    f"?keywords={quote_plus(query)}&origin=GLOBAL_SEARCH_HEADER"
                )
                page.goto(search_url, timeout=20000)
                page.wait_for_timeout(2000)

                # Get first result
                results = page.query_selector_all(".reusable-search__result-container")
                if not results:
                    results = page.query_selector_all("[data-chameleon-result-urn]")

                if results:
                    person = self._extract_person(results[0])
                    if person:
                        sent = self._send_connect(page, person, company, role)
                        if sent:
                            _increment_count()
                            logger.info(
                                f"LinkedIn: connected with {person['name']} @ {company}"
                            )
                            return person
                time.sleep(random.uniform(2, 4))

        except Exception as e:
            logger.error(f"LinkedIn outreach error: {e}")
        return None

    def _extract_person(self, el) -> Optional[Dict]:
        try:
            name_el    = el.query_selector(".actor-name, .entity-result__title-text a span[aria-hidden]")
            title_el   = el.query_selector(".entity-result__primary-subtitle")
            link_el    = el.query_selector("a.app-aware-link, a[href*='/in/']")

            name  = name_el.inner_text().strip() if name_el else ""
            title = title_el.inner_text().strip() if title_el else ""
            href  = link_el.get_attribute("href") if link_el else ""
            url   = href.split("?")[0] if href else ""

            if name and url:
                return {"name": name, "title": title, "profile_url": url}
        except:
            pass
        return None

    def _send_connect(self, page: Page, person: Dict, company: str, role: str) -> bool:
        try:
            page.goto(person["profile_url"], timeout=20000)
            page.wait_for_timeout(2000)

            # Find Connect button
            connect_btn = None
            for sel in [
                "button:has-text('Connect')",
                "button[aria-label*='Connect']",
            ]:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        connect_btn = btn
                        break
                except:
                    pass

            if not connect_btn:
                # Try More → Connect in overflow menu
                for sel in ["button:has-text('More')", "button[aria-label='More actions']"]:
                    try:
                        page.click(sel)
                        page.wait_for_timeout(800)
                        page.click("button:has-text('Connect')")
                        break
                    except:
                        pass

            # Add a personal note
            page.wait_for_timeout(800)
            try:
                note_btn = page.query_selector("button:has-text('Add a note')")
                if note_btn:
                    note_btn.click()
                    page.wait_for_timeout(500)
                    msg = self.template.format(
                        name=person["name"].split()[0],
                        role=role,
                        company=company,
                    )[:300]
                    page.fill("textarea[name='message']", msg)
            except:
                pass

            # Send
            for sel in ["button:has-text('Send')", "button[aria-label='Send now']"]:
                try:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click()
                        page.wait_for_timeout(1000)
                        return True
                except:
                    pass

        except Exception as e:
            logger.debug(f"Connect button interaction: {e}")
        return False
