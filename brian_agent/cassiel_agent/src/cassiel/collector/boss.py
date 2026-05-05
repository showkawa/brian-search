"""BOSS直聘采集器 — Playwright浏览器自动化 (Async)

基于 spike_03_boss.py 验证的模式，实现:
- Cookie登录 / 手动登录
- 关键词搜索
- 分页抓取
- 候选人信息结构化提取

安全约束:
- G-03: headful模式 (可见浏览器)
- G-04: 操作间隔 ≥ 2秒
- G-07: 不存储密码，只存Cookie
- G-08: 搜索间隔 ≥ 5s，翻页间隔 ≥ 3s

错误处理:
- CaptchaError: 验证码拦截 → 用户手动处理
- RateLimitError: 频率限制 → 指数退避
- NetworkError: 网络异常 → 重试或通知
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from pathlib import Path
from typing import Any, Callable

from playwright.async_api import (
    Browser, BrowserContext, Page,
    TimeoutError as PlaywrightTimeout,
    async_playwright,
)

from cassiel.config.settings import SearchConfig
from cassiel.models.candidate import Candidate, CandidateList

logger = logging.getLogger(__name__)


# ── 自定义异常 ──────────────────────────────────────────────

class CollectorError(Exception):
    """采集器异常基类"""


class CaptchaError(CollectorError):
    """验证码拦截 — 需要用户手动处理"""


class RateLimitError(CollectorError):
    """频率限制 — 请求过于频繁"""


class NetworkError(CollectorError):
    """网络异常 — 连接失败/超时"""


class LoginExpiredError(CollectorError):
    """登录过期 — 需要重新登录"""


# ── 常量 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
COOKIES_FILE = BASE_DIR / "brian_agent" / "cassiel_agent" / "cookies.json"
DATA_DIR = BASE_DIR / "brian_agent" / "cassiel_agent" / "data"

BASE_URL = "https://www.zhipin.com"
SEARCH_URL = "https://www.zhipin.com/web/geek/job?query={keyword}&city={city_code}"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class BossCollector:
    """BOSS直聘候选人采集器 (Async)

    Usage:
        collector = BossCollector()
        candidates = await collector.search(keyword="Python开发", city="北京")
        await collector.close()
    """

    def __init__(
        self,
        headless: bool = False,
        cookies_path: Path | str | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.headless = headless
        self.cookies_path = Path(cookies_path) if cookies_path else COOKIES_FILE
        self.on_log = on_log or (lambda msg: logger.info(msg))

        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def _log(self, msg: str) -> None:
        self.on_log(msg)

    # ── 浏览器管理 ──────────────────────────────────────────────

    async def _ensure_browser(self) -> Page:
        if self._page is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=USER_AGENT,
            )
            self._page = await self._context.new_page()
        return self._page

    async def _ensure_context(self) -> BrowserContext:
        if self._context is None:
            await self._ensure_browser()
        return self._context  # type: ignore[return-value]

    # ── Cookie管理 ──────────────────────────────────────────────

    async def load_cookies(self) -> bool:
        context = await self._ensure_context()
        if not self.cookies_path.exists():
            self._log("⚠️ Cookie文件不存在")
            return False
        try:
            cookies = json.loads(self.cookies_path.read_text(encoding="utf-8"))
            await context.add_cookies(cookies)
            self._log(f"✅ 已加载 {len(cookies)} 个Cookie")
            return True
        except Exception as e:
            self._log(f"⚠️ Cookie加载失败: {e}")
            return False

    async def save_cookies(self) -> None:
        context = await self._ensure_context()
        cookies = await context.cookies()
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookies_path.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._log(f"💾 已保存 {len(cookies)} 个Cookie")

    # ── 登录 ──────────────────────────────────────────────

    async def wait_for_login(self, timeout: int = 300_000) -> None:
        """等待用户手动登录，登录成功后自动保存Cookie"""
        page = await self._ensure_browser()
        self._log("🔑 请在浏览器中手动登录BOSS直聘...")
        await page.goto(f"{BASE_URL}/?ka=header-login", wait_until="domcontentloaded")
        await page.wait_for_url("**/web/**", timeout=timeout)
        self._log("✅ 登录成功！")
        await self.save_cookies()

    async def ensure_login(self) -> bool:
        """确保已登录。尝试Cookie登录，失败则等待手动登录"""
        page = await self._ensure_browser()
        cookies_loaded = await self.load_cookies()
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await self._random_delay(2.0, 4.0)

        if not cookies_loaded:
            await self.wait_for_login()
            return True

        await page.reload(wait_until="domcontentloaded")
        await self._random_delay(2.0, 4.0)
        if "login" in page.url.lower():
            self._log("⚠️ Cookie已过期，请重新登录")
            await self.wait_for_login()
            return True

        self._log("✅ Cookie登录成功")
        return True

    async def verify_cookies(self) -> bool:
        """快速验证Cookie是否有效（无头模式，不弹出登录窗）

        Returns:
            True: Cookie有效
            False: Cookie无效或过期
        """
        if not self.cookies_path.exists():
            return False
        try:
            page = await self._ensure_browser()
            await self.load_cookies()
            await page.goto(BASE_URL, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            return "login" not in page.url.lower()
        except Exception:
            return False

    # ── 搜索与抓取 ──────────────────────────────────────────────

    async def search(
        self,
        keyword: str = "Python开发",
        city: str = "北京",
        city_code: str = "100010000",
        max_pages: int = 3,
        config: SearchConfig | None = None,
    ) -> CandidateList:
        if config:
            keyword = config.keyword
            city = config.city
            city_code = config.get_city_code()
            max_pages = config.max_pages

        self._log(f"🔍 开始搜索: {keyword} @ {city}")
        await self.ensure_login()

        search_url = SEARCH_URL.format(keyword=keyword, city_code=city_code)
        page = await self._ensure_browser()

        self._log(f"📍 导航到搜索页: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded")
        await self._random_delay(3.0, 5.0)

        all_candidates = CandidateList(
            search_keyword=keyword,
            search_city=city,
        )

        for page_num in range(1, max_pages + 1):
            self._log(f"📄 正在抓取第 {page_num}/{max_pages} 页...")
            candidates = await self._extract_candidates(page)
            all_candidates.candidates.extend(candidates.candidates)

            if page_num < max_pages:
                if not await self._go_next_page(page):
                    self._log("⚠️ 无法翻到下一页，停止抓取")
                    break
                await self._random_delay(3.0, 5.0)

        all_candidates.total_count = len(all_candidates.candidates)
        self._log(f"✅ 搜索完成，共抓取 {all_candidates.total_count} 位候选人")
        return all_candidates

    async def _extract_candidates(self, page: Page) -> CandidateList:
        candidates = CandidateList()

        try:
            await page.wait_for_selector(".job-list-box", timeout=15_000)
        except Exception:
            self._log("⚠️ 职位列表容器未找到，尝试备选选择器...")
            try:
                await page.wait_for_selector(".search-job-result", timeout=10_000)
            except Exception:
                self._log("❌ 未找到搜索结果，页面可能已改版或登录过期")
                return candidates

        cards = page.query_selector_all(".job-list-box .job-card-wrapper")
        if not cards:
            cards = page.query_selector_all(".search-job-result .job-card-left")

        self._log(f"📋 找到 {len(cards)} 个结果卡片")

        for idx, card in enumerate(cards):
            try:
                candidate = Candidate(
                    name=await self._safe_text(card, ".job-name a, .job-title", ""),
                    title=await self._safe_text(card, ".job-name span, .job-area", ""),
                    salary=await self._safe_text(card, ".salary, .job-salary", ""),
                    experience=await self._safe_text(card, ".tag-list li:nth-child(1), .job-info .tag-list li:first-child", ""),
                    education=await self._safe_text(card, ".tag-list li:nth-child(2), .job-info .tag-list li:nth-child(2)", ""),
                    online_status=await self._safe_text(card, ".job-status, .job-tags", ""),
                    company=await self._safe_text(card, ".company-name a, .info-company a", ""),
                    raw_data={"card_index": idx + 1},
                )
                link_el = card.query_selector("a[href*='/geek/']")
                if link_el:
                    href = await link_el.get_attribute("href") or ""
                    candidate.profile_url = f"{BASE_URL}{href}" if href.startswith("/") else href

                candidates.add(candidate)
            except Exception as e:
                self._log(f"⚠️ 解析卡片 {idx + 1} 失败: {e}")
                continue

        return candidates

    async def _go_next_page(self, page: Page) -> bool:
        try:
            next_btn = page.query_selector(".options-pages .next")
            if next_btn:
                await next_btn.click()
                await page.wait_for_load_state("domcontentloaded")
                return True
        except Exception as e:
            self._log(f"⚠️ 翻页失败: {e}")
        return False

    # ── 页面错误检测 ──────────────────────────────────────

    async def check_page_errors(self, page: Page | None = None) -> None:
        page = page or self._page
        if page is None:
            return
        await self._detect_captcha(page)
        await self._detect_rate_limit(page)
        await self._detect_login_expired(page)
        await self._detect_network_error(page)

    async def _detect_captcha(self, page: Page) -> None:
        captcha_selectors = [
            ".geetest_panel", ".geetest_holder", ".captcha", "#captcha",
            ".verify-code", ".yidun_slider", ".nc_wrapper",
        ]
        for sel in captcha_selectors:
            try:
                el = page.query_selector(sel)
                if el and await el.is_visible():
                    self._log("🔐 检测到验证码! 请在浏览器中完成验证")
                    raise CaptchaError(
                        f"检测到验证码元素 ({sel})，请在浏览器窗口中手动完成验证"
                    )
            except CaptchaError:
                raise
            except Exception:
                continue

    async def _detect_rate_limit(self, page: Page) -> None:
        rate_limit_keywords = [
            "操作频繁", "稍后再试", "请勿频繁", "访问过于频繁",
            "请求过于频繁", "频率限制", "429", "Too Many Requests",
        ]
        try:
            page_text = await page.inner_text("body") or ""
        except Exception:
            return

        for keyword in rate_limit_keywords:
            if keyword in page_text:
                self._log(f"⏱ 检测到频率限制: {keyword}")
                raise RateLimitError(
                    f"触发了 BOSS 直聘频率限制 ('{keyword}')，请等待后重试"
                )

    async def _detect_login_expired(self, page: Page) -> None:
        try:
            url = page.url or ""
        except Exception:
            return
        if any(ind in url.lower() for ind in ["login", "passport", "register"]):
            self._log("🔑 登录已过期")
            raise LoginExpiredError("登录已过期，请重新登录")

    async def _detect_network_error(self, page: Page) -> None:
        try:
            title = await page.title() or ""
        except Exception:
            title = ""
        network_indicators = [
            "无法访问此网站", "ERR_", "连接已重置",
            "No internet", "This site can't be reached",
        ]
        for indicator in network_indicators:
            if indicator.lower() in title.lower():
                self._log(f"🌐 检测到网络错误: {title}")
                raise NetworkError(f"网络错误: {title}")

    # ── 工具方法 ──────────────────────────────────────────────

    @staticmethod
    async def _safe_text(element: Any, selector: str, default: str = "") -> str:
        child = element.query_selector(selector)
        if child:
            return (await child.inner_text() or "").strip()
        return default

    @staticmethod
    async def _random_delay(lo: float = 2.0, hi: float = 5.0) -> None:
        delay = random.uniform(lo, hi)
        await asyncio.sleep(delay)

    # ── 生命周期 ──────────────────────────────────────────────

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._context = None
        self._page = None
        self._log("✅ 浏览器已关闭")

    async def __aenter__(self) -> BossCollector:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
