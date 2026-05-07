"""BOSS直聘 API 客户端 — 纯 HTTP，无需 Playwright

基于 boss-cli (https://github.com/jackwener/boss-cli) 方案:
- Cookie 从本地浏览器提取 (Chrome/Edge/Firefox)
- 候选人搜索通过 /wapi/zpitem/web/boss/search/geek/info 接口
"""

from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
COOKIES_FILE = BASE_DIR / "brian_agent" / "cassiel_agent" / "cookies.json"

BASE_URL = "https://www.zhipin.com"
BOSS_SEARCH_URL = "/wapi/zpitem/web/boss/search/geek/info"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": f"{BASE_URL}/",
    "Origin": BASE_URL,
}

REQUIRED_COOKIES = {"wt2", "wbg", "zp_at"}


class BossAuthError(Exception):
    """登录失败"""


class BossApiClient:
    """BOSS直聘 API 客户端"""

    def __init__(self, cookies: dict[str, str] | None = None) -> None:
        self._cookies = cookies or {}
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={**HEADERS},
            timeout=30,
            follow_redirects=False,
        )
        if self._cookies:
            self._client.cookies.update(self._cookies)

    def close(self) -> None:
        self._client.close()

    @property
    def is_authenticated(self) -> bool:
        return bool(self._cookies and REQUIRED_COOKIES & set(self._cookies.keys()))

    @property
    def cookies(self) -> dict[str, str]:
        return dict(self._cookies)

    # ── Cookie 提取 ──────────────────────────────────────────

    @staticmethod
    def extract_from_browser(browser: str | None = None) -> dict[str, str] | None:
        """从本地浏览器提取 BOSS 直聘 Cookie

        Args:
            browser: 指定浏览器 (chrome/edge/firefox)，None 则自动尝试

        Returns:
            Cookie 字典，或 None
        """
        try:
            import browser_cookie3
        except ImportError:
            logger.error("browser-cookie3 未安装")
            return None

        browsers = [browser] if browser else ["chrome", "edge", "firefox"]

        for name in browsers:
            try:
                loader = getattr(browser_cookie3, name, None)
                if loader is None:
                    continue
                jar = loader(domain_name=".zhipin.com")
                cookies = {c.name: c.value for c in jar if c.domain and "zhipin" in c.domain}
                if REQUIRED_COOKIES & set(cookies.keys()):
                    logger.info("从 %s 提取到 %d 个 Cookie", name, len(cookies))
                    return cookies
                logger.debug("%s: Cookie 不完整 (%s)", name, set(cookies.keys()))
            except Exception as e:
                logger.debug("从 %s 提取失败: %s", name, e)
                continue

        return None

    # ── API 调用 ──────────────────────────────────────────

    def search_candidates(
        self,
        keyword: str = "",
        city: str = "",
        page: int = 1,
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {"page": page, "pageSize": 20}
        if keyword:
            params["query"] = keyword
        if city:
            params["city"] = city

        try:
            resp = self._client.get(
                BOSS_SEARCH_URL,
                params=params,
                headers={"Referer": f"{BASE_URL}/web/chat/recommend"},
            )
            data = resp.json()
            if data.get("code") == 0:
                zpdata = data.get("zpData", {})
                geek_list = zpdata.get("geekList", zpdata.get("resultList", []))
                if not geek_list:
                    logger.warning("搜索返回空结果")
                return zpdata
            else:
                logger.warning("搜索失败: code=%s, msg=%s", data.get("code"), data.get("message"))
                if data.get("code") in (37, 121, 122):
                    raise BossAuthError(f"需要重新登录 (code={data.get('code')})")
                return None
        except BossAuthError:
            raise
        except Exception as e:
            logger.error("搜索请求失败: %s", e)
            return None

    # ── Cookie 持久化 ──────────────────────────────────────────

    def save_cookies(self) -> None:
        if not self._cookies:
            return
        COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIES_FILE.write_text(
            json.dumps(self._cookies, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def load_cookies() -> dict[str, str] | None:
        if not COOKIES_FILE.exists():
            return None
        try:
            return json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
