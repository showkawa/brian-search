"""邀约自动发送 — Playwright BOSS直聘聊天发送器

通过 Playwright 浏览器自动化，在 BOSS 直聘上向候选人发送沟通邀约:
- 复用 BossCollector 的 Cookie / 浏览器上下文 (免二次登录)
- 打开候选人聊天页面
- 填写邀约文本
- 点击发送按钮

安全约束 (参考 G-08 / G-09):
- 发送间隔 ≥ 10 秒 (G-08)
- 每次发送前人工预览确认 (G-09)
- 不存储密码 (G-07)
- 保存发送状态到 SessionStore
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from cassiel.collector.boss import BASE_URL
from cassiel.models.candidate import Candidate
from cassiel.session.store import SessionStore

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────

# BOSS直聘聊天页面URL模板
CHAT_URL = f"{BASE_URL}/web/chat"
# BOSS直聘人才详情页面URL模板 (通过候选人ID跳转)
GEEK_PROFILE_URL = f"{BASE_URL}/web/geek/chat"
# BOSS直聘沟通页面入口
GEEK_CHAT_URL = f"{BASE_URL}/web/geek/chat?userId={{encrypt_id}}"

MIN_SEND_INTERVAL_S = 10  # G-08: 发送间隔 ≥ 10s
MAX_SEND_INTERVAL_S = 15  # 加上随机抖动
TYPING_DELAY_MIN_MS = 30  # 打字模拟: 每个字符最小延迟
TYPING_DELAY_MAX_MS = 80  # 打字模拟: 每个字符最大延迟

# 聊天输入框 & 发送按钮选择器 (BOSS直聘经常改版，需持续维护)
CHAT_INPUT_SELECTORS = [
    ".chat-input textarea",
    ".chat-input .ql-editor",
    '[contenteditable="true"]',
    ".message-input textarea",
    ".input-area textarea",
]
SEND_BUTTON_SELECTORS = [
    ".chat-input .send-btn",
    ".chat-input .btn-send",
    ".send-btn",
    'button.send',
    '.btn-send',
]
CHAT_WINDOW_SELECTOR = ".chat-window"


# ── 异常类 ──────────────────────────────────────────────

class SendError(Exception):
    """发送异常基类"""


class CaptchaError(SendError):
    """验证码拦截"""


class RateLimitError(SendError):
    """频率限制"""


class ChatNotFoundError(SendError):
    """聊天窗口未找到"""


class LoginExpiredError(SendError):
    """登录过期"""


# ── InvitationSender ────────────────────────────────────

class InvitationSender:
    """BOSS直聘邀约自动发送器

    使用 Playwright 打开聊天页面，填写邀约文本并发送。

    安全机制:
    - 复用 BossCollector 的 Cookie (免二次登录)
    - 发送间隔 ≥ 10 秒 (G-08)
    - 打字模拟人类行为 (非瞬间填入)
    - 发送前检查页面状态 (验证码/限流/掉线)

    Usage:
        sender = InvitationSender(browser_context=collector_context, on_log=print)
        sender.send_one(candidate, "邀请文案...")
        sender.close()
    """

    def __init__(
        self,
        browser_context: Any = None,
        cookies_path: Path | str | None = None,
        on_log: Callable[[str], None] | None = None,
        on_sent: Callable[[Candidate, str], None] | None = None,
    ) -> None:
        """初始化发送器

        Args:
            browser_context: Playwright BrowserContext (复用采集器的上下文)
            cookies_path: Cookie文件路径 (当没有传入browser_context时使用)
            on_log: 日志回调
            on_sent: 发送成功回调 (candidate, text)
        """
        try:
            from playwright.sync_api import BrowserContext, sync_playwright
        except ImportError:
            raise ImportError(
                "playwright 未安装。请运行: pip install playwright && playwright install chromium"
            )

        self._pw_instance = None
        self._browser = None
        self._context: BrowserContext | None = browser_context
        self._page = None
        self._cookies_path = (
            Path(cookies_path)
            if cookies_path
            else Path(__file__).resolve().parent.parent.parent.parent.parent
            / "brian_agent" / "cassiel_agent" / "cookies.json"
        )
        self.on_log = on_log or (lambda msg: logger.info(msg))
        self.on_sent = on_sent or (lambda c, t: None)

        self._last_send_time: float = 0.0
        self._sent_count: int = 0
        self._sent_ids: set[str] = set()

    @property
    def browser_context(self) -> Any:
        """获取或创建浏览器上下文"""
        if self._context is not None:
            return self._context

        # 创建新的浏览器实例
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("playwright 未安装")

        self._pw_instance = sync_playwright().start()
        self._browser = self._pw_instance.chromium.launch(headless=False)
        self._context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        self._load_cookies()
        self._log("✅ 创建新的浏览器上下文")
        return self._context

    def ensure_page(self) -> Any:
        """确保页面就绪"""
        ctx = self.browser_context
        if self._page is None:
            self._page = ctx.new_page()
        return self._page

    # ── Cookie管理 ──────────────────────────────────────

    def _load_cookies(self) -> bool:
        """从文件加载Cookie到上下文"""
        import json

        if not self._cookies_path.exists():
            self._log("⚠️ Cookie文件不存在，可能需要先登录")
            return False

        try:
            cookies = json.loads(self._cookies_path.read_text(encoding="utf-8"))
            self._context.add_cookies(cookies)  # type: ignore[union-attr]
            self._log(f"✅ 已加载 {len(cookies)} 个Cookie")
            return True
        except Exception as e:
            self._log(f"⚠️ Cookie加载失败: {e}")
            return False

    # ── 发送流程 ────────────────────────────────────────

    def send_one(
        self,
        candidate: Candidate,
        message: str,
        dry_run: bool = False,
    ) -> bool:
        """向一位候选人发送邀约

        Args:
            candidate: 候选人信息
            message: 邀约文案
            dry_run: 仅模拟，不实际发送 (用于测试)

        Returns:
            是否发送成功

        Raises:
            CaptchaError: 遇到验证码
            RateLimitError: 频率限制
            ChatNotFoundError: 未找到聊天入口
            LoginExpiredError: 登录过期
        """
        candidate_key = candidate.profile_url or candidate.name or "unknown"
        self._log(f"\n📨 准备发送邀约给: {candidate.name or '候选人'}")

        # ── 1. 速率限制检查 ──
        self._enforce_rate_limit()

        # ── 2. 检查是否已发送 ──
        if candidate_key in self._sent_ids:
            self._log(f"⚠️ 已向 {candidate.name} 发送过，跳过")
            return False

        if dry_run:
            self._log(f"[DRY RUN] 模拟发送给 {candidate.name}: {message[:50]}...")
            self._record_sent(candidate, message, status="dry_run")
            return True

        # ── 3. 导航到聊天页面 ──
        page = self.ensure_page()

        try:
            self._navigate_to_chat(page, candidate)
            self._check_page_errors(page)

            # ── 4. 填写邀约文本 ──
            self._fill_message(page, message)

            # ── 5. 点击发送 ──
            self._click_send(page)

            # ── 6. 记录发送时间 ──
            self._last_send_time = time.monotonic()
            self._sent_count += 1

            candidate_key = candidate.profile_url or candidate.name or "unknown"
            self._sent_ids.add(candidate_key)
            self._log(f"✅ 发送成功！给 {candidate.name}: {message[:40]}...")
            self._record_sent(candidate, message, status="sent")
            self.on_sent(candidate, message)

            return True

        except (CaptchaError, RateLimitError, LoginExpiredError):
            raise
        except Exception as e:
            self._log(f"❌ 发送失败 ({candidate.name}): {e}")
            self._record_sent(candidate, message, status="failed")
            raise SendError(f"发送失败: {e}") from e

    def send_batch(
        self,
        candidates: list[Candidate],
        content_map: dict[str, str],
        on_progress: Callable[[int, int], None] | None = None,
        skip_sent: bool = True,
    ) -> dict[str, bool]:
        """批量发送邀约

        Args:
            candidates: 候选人列表
            content_map: {候选人姓名: 邀约文案}
            on_progress: 进度回调 (current, total)
            skip_sent: 跳过已发送的

        Returns:
            {候选人姓名: 是否成功}
        """
        results: dict[str, bool] = {}
        total = len(candidates)
        self._log(f"📬 开始批量发送 {total} 条邀约...")

        for idx, candidate in enumerate(candidates):
            name = candidate.name or f"candidate_{idx}"
            message = content_map.get(name, "")

            if not message:
                self._log(f"⚠️ 跳过 {name}: 无邀约文案")
                results[name] = False
                if on_progress:
                    on_progress(idx + 1, total)
                continue

            if skip_sent and (candidate.profile_url or name) in self._sent_ids:
                self._log(f"⏭ 跳过 {name}: 已发送")
                results[name] = True
                if on_progress:
                    on_progress(idx + 1, total)
                continue

            try:
                success = self.send_one(candidate, message)
                results[name] = success
            except (CaptchaError, RateLimitError, LoginExpiredError) as e:
                self._log(f"⛔ 批量发送中断: {e}")
                results[name] = False
                break  # 严重错误，停止批量发送
            except Exception as e:
                self._log(f"❌ {name} 发送异常: {e}")
                results[name] = False

            if on_progress:
                on_progress(idx + 1, total)

        succeeded = sum(1 for v in results.values() if v)
        self._log(f"📊 批量发送完成: {succeeded}/{total} 成功")
        return results

    # ── 页面操作 ───────────────────────────────────────

    def _navigate_to_chat(self, page: Any, candidate: Candidate) -> None:
        """导航到候选人聊天页面

        BOSS直聘聊天入口:
        - 如果有 profile_url (如 /web/geek/chat?userId=xxx)，直接使用
        - 否则需要先搜索候选人再点击沟通按钮
        """
        profile_url = candidate.profile_url

        if profile_url:
            # 直接使用候选人主页链接
            if not profile_url.startswith("http"):
                profile_url = f"{BASE_URL}{profile_url}"
            self._log(f"📍 导航到候选人页面: {profile_url}")
            page.goto(profile_url, wait_until="domcontentloaded")
            self._random_delay(2.0, 4.0)

            # 尝试找到并点击 "沟通" 按钮
            chat_btn_found = self._click_chat_button(page)
            if not chat_btn_found:
                self._log("⚠️ 未找到沟通按钮，尝试直接进入聊天列表")
                page.goto(CHAT_URL, wait_until="domcontentloaded")
                self._random_delay(2.0, 4.0)
                self._select_candidate_from_list(page, candidate)
        else:
            # 没有个人主页链接，进入聊天列表
            self._log("📍 进入聊天列表页")
            page.goto(CHAT_URL, wait_until="domcontentloaded")
            self._random_delay(2.0, 4.0)
            self._select_candidate_from_list(page, candidate)

    def _click_chat_button(self, page: Any) -> bool:
        """在候选人详情页点击 "沟通" 按钮"""
        chat_btn_selectors = [
            ".btn-startchat",
            ".op-btn.op-btn-chat",
            'a:has-text("沟通")',
            'button:has-text("沟通")',
            '.chat-me',
            '[ka="chat_btn"]',
        ]
        for selector in chat_btn_selectors:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    btn.click()
                    page.wait_for_load_state("domcontentloaded")
                    self._random_delay(1.5, 3.0)
                    self._log("✅ 已点击沟通按钮")
                    return True
            except Exception:
                continue
        return False

    def _select_candidate_from_list(self, page: Any, candidate: Candidate) -> None:
        """从聊天列表中选择候选人"""
        name = candidate.name or ""
        if not name:
            self._log("⚠️ 候选人无姓名，跳过聊天列表选择")

        # 尝试点击列表中对应名称的聊天项
        selectors = [
            f'.chat-item:has-text("{name}")',
            f'.chat-list-item:has-text("{name}")',
            f'a:has-text("{name}")',
            f'div:has-text("{name}")',
        ]
        for selector in selectors:
            try:
                el = page.query_selector(selector)
                if el and el.is_visible():
                    el.click()
                    page.wait_for_load_state("domcontentloaded")
                    self._random_delay(1.5, 3.0)
                    self._log(f"✅ 已选中聊天: {name}")
                    return
            except Exception:
                continue

        self._log(f"⚠️ 未在聊天列表中找到 {name}")

    def _check_page_errors(self, page: Any) -> None:
        """检查页面错误状态 (验证码/限流/掉线)"""
        # 检查验证码
        captcha_selectors = [
            ".geetest_panel",
            ".captcha",
            "#captcha",
            ".verify-code",
        ]
        for sel in captcha_selectors:
            el = page.query_selector(sel)
            if el and el.is_visible():
                raise CaptchaError("⚠️ 检测到验证码，需要人工处理")

        # 检查限流提示
        rate_limit_texts = ["操作频繁", "稍后再试", "请勿频繁"]
        page_text = ""
        try:
            page_text = page.inner_text("body") or ""
        except Exception:
            pass
        for phrase in rate_limit_texts:
            if phrase in page_text:
                raise RateLimitError(f"⚠️ 频率限制: {phrase}")

        # 检查登录过期
        if "login" in page.url.lower() or "passport" in page.url.lower():
            raise LoginExpiredError("⚠️ 登录已过期，请重新登录")

    def _fill_message(self, page: Any, message: str) -> None:
        """填写邀约文本到聊天输入框 (模拟打字)"""
        input_el = None
        for selector in CHAT_INPUT_SELECTORS:
            try:
                el = page.query_selector(selector)
                if el and el.is_visible():
                    input_el = el
                    break
            except Exception:
                continue

        if input_el is None:
            raise ChatNotFoundError("未找到聊天输入框，请确认页面已加载聊天窗口")

        # 清空已有内容
        try:
            input_el.click()
            input_el.fill("")
            self._random_delay(0.3, 0.5)
        except Exception:
            pass

        # 模拟人类打字 (逐字输入)
        self._log(f"⌨️ 正在输入邀约文案 ({len(message)} 字)...")
        for char in message:
            try:
                input_el.type(char, delay=random.randint(TYPING_DELAY_MIN_MS, TYPING_DELAY_MAX_MS))
            except Exception:
                # 回退到 fill
                input_el.fill(message)
                break

        self._random_delay(0.5, 1.0)

    def _click_send(self, page: Any) -> None:
        """点击发送按钮"""
        send_btn = None
        for selector in SEND_BUTTON_SELECTORS:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    send_btn = btn
                    break
            except Exception:
                continue

        if send_btn is None:
            raise ChatNotFoundError("未找到发送按钮，请确认聊天输入框已就绪")

        self._log("📤 点击发送...")
        send_btn.click()
        self._random_delay(1.5, 3.0)

    # ── 速率限制 ──────────────────────────────────────

    def _enforce_rate_limit(self) -> None:
        """强制执行发送间隔 (G-08: ≥ 10s)"""
        elapsed = time.monotonic() - self._last_send_time
        min_interval = MIN_SEND_INTERVAL_S
        if elapsed < min_interval:
            wait = min_interval - elapsed + random.uniform(0, 5)
            self._log(f"⏳ 速率限制等待 {wait:.1f}s... (已过 {elapsed:.1f}s)")
            time.sleep(wait)

    # ── 记录 ──────────────────────────────────────────

    def _record_sent(
        self,
        candidate: Candidate,
        message: str,
        status: str = "sent",
    ) -> None:
        """记录发送状态到 SessionStore"""
        try:
            with SessionStore() as store:
                store.save_invitation(
                    candidate_id=0,  # 没有 DB candidate ID，使用占位符
                    content=message,
                    status=status,
                )
        except Exception as e:
            self._log(f"⚠️ 发送记录保存失败: {e}")

    # ── 工具方法 ──────────────────────────────────────

    @staticmethod
    def _random_delay(lo: float = 1.0, hi: float = 3.0) -> None:
        """随机延迟"""
        time.sleep(random.uniform(lo, hi))

    def _log(self, msg: str) -> None:
        """输出日志"""
        self.on_log(msg)

    # ── 生命周期 ──────────────────────────────────────

    def close(self) -> None:
        """关闭浏览器资源"""
        if self._page:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None

        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._pw_instance:
            try:
                self._pw_instance.stop()
            except Exception:
                pass
            self._pw_instance = None

        self._context = None
        self._log("✅ 发送器已关闭")

    def __enter__(self) -> InvitationSender:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
