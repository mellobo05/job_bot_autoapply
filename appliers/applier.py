"""
Auto-Applier
Uses Playwright to fill and submit applications on each ATS platform.
Handles Greenhouse, Ashby, Workable, and generic form patterns.
"""

import logging
import time
import json
from pathlib import Path
from typing import Dict, Optional
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PWTimeout

logger = logging.getLogger("applier")


class AutoApplier:
    def __init__(self, user: dict):
        self.user = user

    def apply(self, job: Dict) -> bool:
        """
        Attempt to apply to a job.
        Returns True on success, False on failure.
        """
        platform = job.get("platform", "").lower()
        url      = job.get("url", "")

        if not url:
            return False

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                if "greenhouse" in url or platform == "greenhouse":
                    return self._apply_greenhouse(browser, job)
                elif "ashby" in url or platform == "ashby":
                    return self._apply_ashby(browser, job)
                elif "workable" in url or platform == "workable":
                    return self._apply_workable(browser, job)
                elif "jobvite" in url or platform == "jobvite":
                    return self._apply_jobvite(browser, job)
                elif "breezy" in url or platform == "breezy":
                    return self._apply_breezy(browser, job)
                elif "lever" in url:
                    return self._apply_lever(browser, job)
                else:
                    return self._apply_generic(browser, job)
            except Exception as e:
                logger.error(f"Apply failed [{job.get('company')}]: {e}")
                return False
            finally:
                browser.close()

    # ── Helpers ─────────────────────────────────────────────
    def _fill_text(self, page: Page, selector: str, value: str, timeout=5000):
        try:
            el = page.wait_for_selector(selector, timeout=timeout)
            el.fill(value)
        except:
            pass

    def _click(self, page: Page, selector: str, timeout=5000):
        try:
            el = page.wait_for_selector(selector, timeout=timeout)
            el.click()
        except:
            pass

    def _upload_resume(self, page: Page):
        resume = self.user.get("resume_path", "")
        if not Path(resume).exists():
            logger.warning("Resume file not found — skipping upload")
            return
        selectors = [
            "input[type='file'][accept*='pdf']",
            "input[type='file'][name*='resume']",
            "input[type='file'][name*='cv']",
            "input[type='file']",
        ]
        for sel in selectors:
            try:
                page.set_input_files(sel, resume)
                logger.info("Resume uploaded")
                return
            except:
                pass
        logger.warning("Could not find resume upload field")

    def _try_submit(self, page: Page) -> bool:
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Send Application')",
            "[data-qa='btn-submit']",
            ".submit-btn",
        ]
        for sel in submit_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(2000)
                    logger.info("Application submitted")
                    return True
            except:
                pass
        return False

    def _fill_common_fields(self, page: Page):
        """Fill fields that appear on most ATS forms."""
        u = self.user
        mappings = [
            # Name
            (["input[name='first_name']","#first_name","[placeholder*='First']"], u.get("name","").split()[0]),
            (["input[name='last_name']", "#last_name","[placeholder*='Last']"],
             u.get("name","").split()[-1] if len(u.get("name","").split()) > 1 else ""),
            # Email
            (["input[type='email']","input[name='email']","#email"], u.get("email","")),
            # Phone
            (["input[type='tel']","input[name='phone']","#phone"], u.get("phone","")),
            # LinkedIn
            (["input[name='linkedin']","input[placeholder*='LinkedIn']","#linkedin_profile"], u.get("linkedin_url","")),
            # Location
            (["input[name='location']","#location","[placeholder*='Location']","[placeholder*='City']"],
             u.get("location","Remote")),
        ]
        for selectors, value in mappings:
            if not value:
                continue
            for sel in selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.fill(str(value))
                        break
                except:
                    pass

    # ── Platform-Specific Appliers ───────────────────────────
    def _apply_greenhouse(self, browser: Browser, job: Dict) -> bool:
        page = browser.new_page()
        page.goto(job["url"], timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        # Click "Apply for this Job" button
        for sel in ["a:has-text('Apply')","button:has-text('Apply')","#apply"]:
            try:
                btn = page.query_selector(sel)
                if btn:
                    btn.click()
                    page.wait_for_timeout(1500)
                    break
            except:
                pass

        self._fill_common_fields(page)
        self._upload_resume(page)

        # Cover letter
        cl_path = self.user.get("cover_letter","")
        if Path(cl_path).exists():
            try:
                cl_text = Path(cl_path).read_text()
                for sel in ["textarea[name='cover_letter']","#cover_letter","textarea"]:
                    el = page.query_selector(sel)
                    if el:
                        el.fill(cl_text)
                        break
            except:
                pass

        # Work authorization dropdowns
        for sel in ["select[name*='work_auth']","select[id*='work_auth']"]:
            try:
                page.select_option(sel, "1")
            except:
                pass

        success = self._try_submit(page)
        page.close()
        return success

    def _apply_ashby(self, browser: Browser, job: Dict) -> bool:
        page = browser.new_page()
        page.goto(job["url"], timeout=25000, wait_until="networkidle")
        page.wait_for_timeout(2000)

        self._fill_common_fields(page)
        self._upload_resume(page)

        success = self._try_submit(page)
        page.close()
        return success

    def _apply_workable(self, browser: Browser, job: Dict) -> bool:
        page = browser.new_page()
        page.goto(job["url"], timeout=25000, wait_until="networkidle")
        page.wait_for_timeout(2000)

        # Workable has a "Apply Now" button that opens modal
        self._click(page, "button:has-text('Apply Now')", timeout=5000)
        page.wait_for_timeout(1500)

        self._fill_common_fields(page)
        self._upload_resume(page)

        success = self._try_submit(page)
        page.close()
        return success

    def _apply_lever(self, browser: Browser, job: Dict) -> bool:
        page = browser.new_page()
        page.goto(job["url"], timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        self._fill_common_fields(page)
        self._upload_resume(page)

        success = self._try_submit(page)
        page.close()
        return success

    def _apply_jobvite(self, browser: Browser, job: Dict) -> bool:
        page = browser.new_page()
        page.goto(job["url"], timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        self._fill_common_fields(page)
        self._upload_resume(page)

        # Jobvite sometimes has multi-step — handle Next buttons
        for _ in range(4):
            for sel in ["button:has-text('Next')","button:has-text('Continue')"]:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(1500)
                        self._fill_common_fields(page)
                        break
                except:
                    pass

        success = self._try_submit(page)
        page.close()
        return success

    def _apply_breezy(self, browser: Browser, job: Dict) -> bool:
        page = browser.new_page()
        page.goto(job["url"], timeout=25000, wait_until="networkidle")
        page.wait_for_timeout(2000)

        self._click(page, "button.apply-button, a.apply")
        page.wait_for_timeout(1000)

        self._fill_common_fields(page)
        self._upload_resume(page)

        success = self._try_submit(page)
        page.close()
        return success

    def _apply_generic(self, browser: Browser, job: Dict) -> bool:
        """Fallback: best-effort form filler for unknown ATS."""
        page = browser.new_page()
        try:
            page.goto(job["url"], timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            # Click any visible Apply button first
            for sel in [
                "a:has-text('Apply Now')", "button:has-text('Apply Now')",
                "a:has-text('Apply')", "button:has-text('Apply')",
            ]:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(1500)
                        break
                except:
                    pass

            self._fill_common_fields(page)
            self._upload_resume(page)
            success = self._try_submit(page)
        except Exception as e:
            logger.warning(f"Generic apply error: {e}")
            success = False
        finally:
            page.close()
        return success
