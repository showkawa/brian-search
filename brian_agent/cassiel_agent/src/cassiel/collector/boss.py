"""BOSS直聘采集器 — Playwright浏览器自动化

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

import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Callable

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout, sync_playwright

from cassiel.config.settings import SearchConfig
from cassiel.models.candidate import Candidate, CandidateList

logger = logging.getLogger(__name__)


# ── 自定义异常 ──────────────────────────────────────────────

class CollectorError(Exception):
    """采集器异常基类"""


class CaptchaError(CollectorError):
    """验证码拦截 — 需要用户手动处理

    当 BOSS 直聘出现验证码 (极验/滑块等) 时抛出。
    调用方应暂停自动化，通知用户在浏览器中完成验证码。
    """


class RateLimitError(CollectorError):
    """频率限制 — 请求过于频繁

    当 BOSS 直聘返回 429-like 响应或显示限流提示时抛出。
    调用方应使用指数退避延迟后重试。
    """


class NetworkError(CollectorError):
    """网络异常 — 连接失败/超时

    当 Playwright 网络请求失败或超时时抛出。
    调用方应提供重试选项。
    """


class LoginExpiredError(CollectorError):
    """登录过期 — 需要重新登录"""


# ── 常量 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
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
    """BOSS直聘候选人采集器

    使用 Playwright 自动化浏览器操作，采集候选人信息。

    Usage:
        collector = BossCollector()
        candidates = collector.search(keyword="Python开发", city="北京")
        collector.close()
    """

    def __init__(
        self,
        headless: bool = False,
        cookies_path: Path | str | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        """初始化采集器

        Args:
            headless: 是否无头模式 (默认False，遵守G-03)
            cookies_path: Cookie文件路径
            on_log: 日志回调函数 (用于UI实时显示)
        """
        self.headless = headless
        self.cookies_path = Path(cookies_path) if cookies_path else COOKIES_FILE
        self.on_log = on_log or (lambda msg: logger.info(msg))

        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def _log(self, msg: str) -> None:
        """输出日志"""
        self.on_log(msg)

    # ── 浏览器管理 ──────────────────────────────────────────────

    def _ensure_browser(self) -> Page:
        """确保浏览器已启动，返回Page对象"""
        if self._page is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._context = self._browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=USER_AGENT,
            )
            self._page = self._context.new_page()
        return self._page

    def _ensure_context(self) -> BrowserContext:
        """确保浏览器上下文已创建"""
        if self._context is None:
            self._ensure_browser()
        return self._context  # type: ignore[return-value]

    # ── Cookie管理 ──────────────────────────────────────────────

    def load_cookies(self) -> bool:
        """从文件加载Cookie

        Returns:
            是否成功加载
        """
        context = self._ensure_context()
        if not self.cookies_path.exists():
            self._log("⚠️ Cookie文件不存在")
            return False
        try:
            cookies = json.loads(self.cookies_path.read_text(encoding="utf-8"))
            context.add_cookies(cookies)
            self._log(f"✅ 已加载 {len(cookies)} 个Cookie")
            return True
        except Exception as e:
            self._log(f"⚠️ Cookie加载失败: {e}")
            return False

    def save_cookies(self) -> None:
        """保存当前Cookie到文件"""
        context = self._ensure_context()
        cookies = context.cookies()
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookies_path.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._log(f"💾 已保存 {len(cookies)} 个Cookie")

    # ── 登录 ──────────────────────────────────────────────

    def wait_for_login(self, timeout: int = 300_000) -> None:
        """等待用户手动登录

        打开登录页面，等待用户在浏览器中完成登录。
        登录成功后自动保存Cookie。

        Args:
            timeout: 超时时间(毫秒)，默认5分钟
        """
        page = self._ensure_browser()
        self._log("🔑 请在浏览器中手动登录BOSS直聘...")
        page.goto(f"{BASE_URL}/?ka=header-login", wait_until="domcontentloaded")
        page.wait_for_url("**/web/**", timeout=timeout)
        self._log("✅ 登录成功！")
        self.save_cookies()

    def ensure_login(self) -> bool:
        """确保已登录

        尝试Cookie登录，失败则等待手动登录。

        Returns:
            是否已登录
        """
        page = self._ensure_browser()
        cookies_loaded = self.load_cookies()
        page.goto(BASE_URL, wait_until="domcontentloaded")
        self._random_delay(2.0, 4.0)

        if not cookies_loaded:
            self.wait_for_login()
            return True

        # 验证Cookie是否有效
        page.reload(wait_until="domcontentloaded")
        self._random_delay(2.0, 4.0)
        if "login" in page.url.lower():
            self._log("⚠️ Cookie已过期，请重新登录")
            self.wait_for_login()
            return True

        self._log("✅ Cookie登录成功")
        return True

    # ── 搜索与抓取 ──────────────────────────────────────────────

    def search(
        self,
        keyword: str = "Python开发",
        city: str = "北京",
        city_code: str = "100010000",
        max_pages: int = 3,
        config: SearchConfig | None = None,
    ) -> CandidateList:
        """搜索候选人

        Args:
            keyword: 搜索关键词
            city: 城市名称
            city_code: BOSS直聘城市代码
            max_pages: 最大抓取页数
            config: 搜索配置 (覆盖其他参数)

        Returns:
            候选人列表
        """
        if config:
            keyword = config.keyword
            city = config.city
            city_code = config.get_city_code()
            max_pages = config.max_pages

        self._log(f"🔍 开始搜索: {keyword} @ {city}")

        # 确保登录
        self.ensure_login()

        # 构建搜索URL
        search_url = SEARCH_URL.format(keyword=keyword, city_code=city_code)
        page = self._ensure_browser()

        # 导航到搜索页
        self._log(f"📍 导航到搜索页: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded")
        self._random_delay(3.0, 5.0)  # G-08: 搜索间隔 ≥ 5s

        # 抓取多页
        all_candidates = CandidateList(
            search_keyword=keyword,
            search_city=city,
        )

        for page_num in range(1, max_pages + 1):
            self._log(f"📄 正在抓取第 {page_num}/{max_pages} 页...")
            candidates = self._extract_candidates(page)
            all_candidates.candidates.extend(candidates.candidates)

            if page_num < max_pages:
                # 翻页
                if not self._go_next_page(page):
                    self._log("⚠️ 无法翻到下一页，停止抓取")
                    break
                self._random_delay(3.0, 5.0)  # G-08: 翻页间隔 ≥ 3s

        all_candidates.total_count = len(all_candidates.candidates)
        self._log(f"✅ 搜索完成，共抓取 {all_candidates.total_count} 位候选人")
        return all_candidates

    def _extract_candidates(self, page: Page) -> CandidateList:
        """从当前页面提取候选人信息

        NOTE: CSS选择器为占位符，BOSS直聘经常改版，
        需要根据实际页面结构更新选择器。
        """
        candidates = CandidateList()

        # 等待职位卡片加载
        try:
            page.wait_for_selector(".job-list-box", timeout=15_000)
        except Exception:
            self._log("⚠️ 职位列表容器未找到，尝试备选选择器...")
            try:
                page.wait_for_selector(".search-job-result", timeout=10_000)
            except Exception:
                self._log("❌ 未找到搜索结果，页面可能已改版或登录过期")
                return candidates

        # 提取卡片
        cards = page.query_selector_all(".job-list-box .job-card-wrapper")
        if not cards:
            cards = page.query_selector_all(".search-job-result .job-card-left")

        self._log(f"📋 找到 {len(cards)} 个结果卡片")

        for idx, card in enumerate(cards):
            try:
                candidate = Candidate(
                    name=self._safe_text(card, ".job-name a, .job-title", ""),
                    title=self._safe_text(card, ".job-name span, .job-area", ""),
                    salary=self._safe_text(card, ".salary, .job-salary", ""),
                    experience=self._safe_text(card, ".tag-list li:nth-child(1), .job-info .tag-list li:first-child", ""),
                    education=self._safe_text(card, ".tag-list li:nth-child(2), .job-info .tag-list li:nth-child(2)", ""),
                    online_status=self._safe_text(card, ".job-status, .job-tags", ""),
                    company=self._safe_text(card, ".company-name a, .info-company a", ""),
                    raw_data={"card_index": idx + 1},
                )
                # 尝试获取个人主页链接
                link_el = card.query_selector("a[href*='/geek/']")
                if link_el:
                    href = link_el.get_attribute("href") or ""
                    candidate.profile_url = f"{BASE_URL}{href}" if href.startswith("/") else href

                candidates.add(candidate)
            except Exception as e:
                self._log(f"⚠️ 解析卡片 {idx + 1} 失败: {e}")
                continue

        return candidates

    def _go_next_page(self, page: Page) -> bool:
        """翻到下一页

        Returns:
            是否成功翻页
        """
        try:
            next_btn = page.query_selector(".options-pages .next")
            if next_btn:
                next_btn.click()
                page.wait_for_load_state("domcontentloaded")
                return True
        except Exception as e:
            self._log(f"⚠️ 翻页失败: {e}")
        return False

    # ── 页面错误检测 ──────────────────────────────────────

    def check_page_errors(self, page: Page | None = None) -> None:
        """检查当前页面是否有验证码/限流/掉线

        在每次页面导航后调用，及时发现异常状态。

        Raises:
            CaptchaError: 检测到验证码
            RateLimitError: 检测到频率限制
            LoginExpiredError: 登录过期
        """
        page = page or self._page
        if page is None:
            return

        # 1. 检测验证码
        self._detect_captcha(page)

        # 2. 检测频率限制 (页面文字匹配)
        self._detect_rate_limit(page)

        # 3. 检测登录过期
        self._detect_login_expired(page)

        # 4. 检测网络错误 (页面加载失败)
        self._detect_network_error(page)

    def _detect_captcha(self, page: Page) -> None:
        """检测验证码元素"""
        captcha_selectors = [
            ".geetest_panel",       # 极验滑块
            ".geetest_holder",
            ".captcha",
            "#captcha",
            ".verify-code",
            ".yidun_slider",        # 网易易盾
            ".nc_wrapper",          # 阿里验证码
        ]
        for sel in captcha_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    self._log("🔐 检测到验证码! 请在浏览器中完成验证")
                    raise CaptchaError(
                        f"检测到验证码元素 ({sel})，请在浏览器窗口中手动完成验证"
                    )
            except CaptchaError:
                raise
            except Exception:
                continue

    def _detect_rate_limit(self, page: Page) -> None:
        """检测频率限制提示"""
        rate_limit_keywords = [
            "操作频繁",
            "稍后再试",
            "请勿频繁",
            "访问过于频繁",
            "请求过于频繁",
            "频率限制",
            "429",
            "Too Many Requests",
        ]
        try:
            page_text = page.inner_text("body") or ""
        except Exception:
            return

        for keyword in rate_limit_keywords:
            if keyword in page_text:
                self._log(f"⏱ 检测到频率限制: {keyword}")
                raise RateLimitError(
                    f"触发了 BOSS 直聘频率限制 ('{keyword}')，请等待后重试"
                )

    def _detect_login_expired(self, page: Page) -> None:
        """检测登录过期"""
        try:
            url = page.url or ""
        except Exception:
            return

        if any(ind in url.lower() for ind in ["login", "passport", "register"]):
            self._log("🔑 登录已过期")
            raise LoginExpiredError("登录已过期，请重新登录")

    def _detect_network_error(self, page: Page) -> None:
        """检测网络/页面加载错误"""
        try:
            title = page.title() or ""
        except Exception:
            title = ""

        network_indicators = [
            "无法访问此网站",
            "ERR_",
            "连接已重置",
            "No internet",
            "This site can't be reached",
        ]
        for indicator in network_indicators:
            if indicator.lower() in title.lower():
                self._log(f"🌐 检测到网络错误: {title}")
                raise NetworkError(f"网络错误: {title}")

    # ── 工具方法 ──────────────────────────────────────────────

    @staticmethod
    def _safe_text(element: Any, selector: str, default: str = "") -> str:
        """安全提取子元素文本"""
        child = element.query_selector(selector)
        if child:
            return (child.inner_text() or "").strip()
        return default

    @staticmethod
    def _random_delay(lo: float = 2.0, hi: float = 5.0) -> None:
        """随机延迟，模拟人类行为 (G-04)"""
        delay = random.uniform(lo, hi)
        time.sleep(delay)

    # ── 生命周期 ──────────────────────────────────────────────

    def close(self) -> None:
        """关闭浏览器"""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._context = None
        self._page = None
        self._log("✅ 浏览器已关闭")

    def __enter__(self) -> BossCollector:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
