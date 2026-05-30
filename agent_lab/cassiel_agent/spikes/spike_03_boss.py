"""
Spike 03: BOSS Zhipin Candidate Search Automation
Phase 0.3 validation script for Cassiel Agent project.

Usage:
    pip install playwright && playwright install chromium
    python brian_agent/cassiel_agent/spikes/spike_03_boss.py
    python brian_agent/cassiel_agent/spikes/spike_03_boss.py --keyword "Python开发"
"""

import json
import random
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # project root
COOKIES_FILE = BASE_DIR / "brian_agent" / "cassiel_agent" / "cookies.json"
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "candidates.json"

# ── Config ─────────────────────────────────────────────────────────────
BASE_URL = "https://www.zhipin.com"
SEARCH_URL = "https://www.zhipin.com/web/geek/job?query={keyword}&city=100010000"
DEFAULT_KEYWORD = "Python开发"


def random_delay(lo: float = 2.0, hi: float = 5.0) -> None:
    """Sleep for a random duration to mimic human behavior."""
    delay = random.uniform(lo, hi)
    print(f"  ⏳ waiting {delay:.1f}s ...")
    time.sleep(delay)


def load_cookies(context) -> bool:
    """Load cookies from cookies.json if it exists. Returns True if loaded."""
    if not COOKIES_FILE.exists():
        return False
    try:
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        context.add_cookies(cookies)
        print(f"  ✅ Loaded {len(cookies)} cookies from {COOKIES_FILE}")
        return True
    except Exception as e:
        print(f"  ⚠️ Failed to load cookies: {e}")
        return False


def save_cookies(context) -> None:
    """Persist current browser cookies to cookies.json."""
    cookies = context.cookies()
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  💾 Saved {len(cookies)} cookies to {COOKIES_FILE}")


def wait_for_login(page) -> None:
    """Open login page and wait until user logs in manually."""
    print("\n  🔑 No valid cookies found. Opening login page ...")
    print("  👉 Please log in manually in the browser window.")
    print("  👉 After login is complete, the script will continue automatically.\n")
    page.goto(f"{BASE_URL}/?ka=header-login", wait_until="domcontentloaded")
    # Wait for the URL to change away from login page (user completed login)
    page.wait_for_url("**/web/**", timeout=300_000)  # 5 min timeout
    print("  ✅ Login detected!")


def extract_candidates(page) -> list[dict]:
    """
    Extract candidate/job data from search result cards.

    NOTE: CSS selectors are placeholders — BOSS Zhipin frequently changes
    their DOM structure. You will need to inspect the actual page and update
    the selectors accordingly.
    """
    candidates = []

    # Wait for job cards to appear
    try:
        page.wait_for_selector(".job-list-box", timeout=15_000)
    except Exception:
        print("  ⚠️ Job list container not found. Trying alternative selectors ...")
        try:
            page.wait_for_selector(".search-job-result", timeout=10_000)
        except Exception:
            print("  ❌ Could not find job results. Page may have changed or login expired.")
            return candidates

    # Primary selector path (placeholder — adjust after inspecting live page)
    cards = page.query_selector_all(".job-list-box .job-card-wrapper")
    if not cards:
        # Fallback selector
        cards = page.query_selector_all(".search-job-result .job-card-left")

    print(f"  📋 Found {len(cards)} result cards")

    for idx, card in enumerate(cards):
        try:
            candidate = {
                "index": idx + 1,
                "name": _safe_text(card, ".job-name a, .job-title", "N/A"),
                "title": _safe_text(card, ".job-name span, .job-area", "N/A"),
                "salary": _safe_text(card, ".salary, .job-salary", "N/A"),
                "experience": _safe_text(card, ".tag-list li:nth-child(1), .job-info .tag-list li:first-child", "N/A"),
                "education": _safe_text(card, ".tag-list li:nth-child(2), .job-info .tag-list li:nth-child(2)", "N/A"),
                "online_status": _safe_text(card, ".job-status, .job-tags", ""),
                "company": _safe_text(card, ".company-name a, .info-company a", "N/A"),
            }
            candidates.append(candidate)
        except Exception as e:
            print(f"  ⚠️ Error parsing card {idx + 1}: {e}")
            continue

    return candidates


def _safe_text(element, selector: str, default: str = "") -> str:
    """Safely extract text content from a child element."""
    child = element.query_selector(selector)
    if child:
        return (child.inner_text() or "").strip()
    return default


def save_results(candidates: list[dict]) -> None:
    """Save extracted candidates to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  💾 Saved {len(candidates)} candidates to {OUTPUT_FILE}")


def main(keyword: str = DEFAULT_KEYWORD) -> None:
    print(f"\n{'='*60}")
    print(f"  BOSS Zhipin Candidate Search Spike")
    print(f"  Keyword: {keyword}")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        # ── Launch headful browser ──────────────────────────────────
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # ── Cookie login or manual login ────────────────────────────
        cookies_loaded = load_cookies(context)
        page.goto(BASE_URL, wait_until="domcontentloaded")
        random_delay()

        if not cookies_loaded:
            # Check if we're actually logged in (cookie might be expired)
            wait_for_login(page)
            save_cookies(context)
        else:
            # Verify cookies are still valid
            page.reload(wait_until="domcontentloaded")
            random_delay()
            # If redirected to login, cookies expired
            if "login" in page.url.lower():
                print("  ⚠️ Cookies expired. Please log in again.")
                wait_for_login(page)
                save_cookies(context)

        # ── Search ──────────────────────────────────────────────────
        search_url = SEARCH_URL.format(keyword=keyword)
        print(f"\n  🔍 Navigating to search: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded")
        random_delay()

        # ── Extract ─────────────────────────────────────────────────
        candidates = extract_candidates(page)

        # ── Display results ─────────────────────────────────────────
        print(f"\n{'─'*60}")
        print(f"  Results ({len(candidates)} candidates)")
        print(f"{'─'*60}")
        for c in candidates:
            print(
                f"  [{c['index']}] {c['name']} | {c['salary']} | "
                f"{c['experience']} | {c['education']} | {c['company']}"
            )

        # ── Save ────────────────────────────────────────────────────
        if candidates:
            save_results(candidates)
        else:
            print("\n  ⚠️ No candidates extracted. Selectors may need updating.")
            print("  💡 Open DevTools on the search page and update CSS selectors in this script.")

        # ── Keep browser open for inspection ────────────────────────
        print("\n  👀 Browser stays open for inspection. Press Ctrl+C to close.")
        try:
            page.wait_for_timeout(600_000)  # 10 min
        except KeyboardInterrupt:
            pass

        browser.close()

    print("\n  ✅ Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BOSS Zhipin Candidate Search Spike")
    parser.add_argument(
        "--keyword", "-k",
        default=DEFAULT_KEYWORD,
        help=f"Search keyword (default: {DEFAULT_KEYWORD})",
    )
    args = parser.parse_args()
    main(keyword=args.keyword)
