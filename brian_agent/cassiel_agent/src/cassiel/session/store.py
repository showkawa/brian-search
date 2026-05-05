"""会话持久化 — SQLite存储搜索历史与候选人缓存

功能:
- 搜索历史记录
- 候选人数据缓存 (避免重复抓取)
- 邀约发送记录
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from cassiel.models.candidate import Candidate, CandidateList

logger = logging.getLogger(__name__)

# ── 默认数据库路径 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
DEFAULT_DB_PATH = BASE_DIR / "brian_agent" / "cassiel_agent" / "data" / "cassiel.db"


class SessionStore:
    """SQLite会话存储

    管理搜索历史、候选人缓存和邀约记录。
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_tables(self) -> None:
        """初始化数据库表"""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    city TEXT NOT NULL,
                    city_code TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    result_count INTEGER DEFAULT 0,
                    config_json TEXT DEFAULT '{}'
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id INTEGER NOT NULL,
                    name TEXT DEFAULT '',
                    title TEXT DEFAULT '',
                    salary TEXT DEFAULT '',
                    experience TEXT DEFAULT '',
                    education TEXT DEFAULT '',
                    online_status TEXT DEFAULT '',
                    profile_url TEXT DEFAULT '',
                    company TEXT DEFAULT '',
                    score REAL,
                    score_reason TEXT DEFAULT '',
                    is_selected INTEGER DEFAULT 0,
                    raw_data TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (search_id) REFERENCES search_history(id)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER NOT NULL,
                    content TEXT DEFAULT '',
                    status TEXT DEFAULT 'draft',
                    sent_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (candidate_id) REFERENCES candidates(id)
                )
            """)
        logger.info("数据库初始化完成: %s", self.db_path)

    # ── 搜索历史 ──────────────────────────────────────────────

    def save_search(
        self,
        keyword: str,
        city: str,
        city_code: str = "",
        result_count: int = 0,
        config: dict[str, Any] | None = None,
    ) -> int:
        """保存搜索记录

        Returns:
            搜索记录ID
        """
        now = datetime.now().isoformat()
        config_json = json.dumps(config or {}, ensure_ascii=False)
        cursor = self.conn.execute(
            """INSERT INTO search_history (keyword, city, city_code, created_at, result_count, config_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (keyword, city, city_code, now, result_count, config_json),
        )
        self.conn.commit()
        search_id = cursor.lastrowid or 0
        logger.info("搜索记录已保存: id=%d, keyword=%s", search_id, keyword)
        return search_id

    def get_search_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """获取搜索历史"""
        rows = self.conn.execute(
            """SELECT id, keyword, city, created_at, result_count
               FROM search_history ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── 候选人缓存 ──────────────────────────────────────────────

    def save_candidates(self, search_id: int, candidates: CandidateList) -> None:
        """保存候选人列表"""
        now = datetime.now().isoformat()
        for c in candidates.candidates:
            self.conn.execute(
                """INSERT INTO candidates
                   (search_id, name, title, salary, experience, education,
                    online_status, profile_url, company, score, score_reason,
                    is_selected, raw_data, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    search_id, c.name, c.title, c.salary, c.experience,
                    c.education, c.online_status, c.profile_url, c.company,
                    c.score, c.score_reason, int(c.is_selected),
                    json.dumps(c.raw_data, ensure_ascii=False), now,
                ),
            )
        self.conn.commit()
        logger.info("已保存 %d 位候选人 (search_id=%d)", len(candidates.candidates), search_id)

    def get_candidates(self, search_id: int) -> CandidateList:
        """获取某次搜索的候选人列表"""
        rows = self.conn.execute(
            """SELECT name, title, salary, experience, education,
                      online_status, profile_url, company, score,
                      score_reason, is_selected, raw_data
               FROM candidates WHERE search_id = ?
               ORDER BY score DESC NULLS LAST""",
            (search_id,),
        ).fetchall()

        candidates = CandidateList(search_keyword="", search_city="")
        for r in rows:
            raw = {}
            try:
                raw = json.loads(r["raw_data"]) if r["raw_data"] else {}
            except json.JSONDecodeError:
                pass
            candidates.add(Candidate(
                name=r["name"],
                title=r["title"],
                salary=r["salary"],
                experience=r["experience"],
                education=r["education"],
                online_status=r["online_status"],
                profile_url=r["profile_url"],
                company=r["company"],
                score=r["score"],
                score_reason=r["score_reason"] or "",
                is_selected=bool(r["is_selected"]),
                raw_data=raw,
            ))
        return candidates

    # ── 邀约记录 ──────────────────────────────────────────────

    def save_invitation(
        self,
        candidate_id: int,
        content: str,
        status: str = "draft",
    ) -> int:
        """保存邀约记录"""
        now = datetime.now().isoformat()
        cursor = self.conn.execute(
            """INSERT INTO invitations (candidate_id, content, status, created_at)
               VALUES (?, ?, ?, ?)""",
            (candidate_id, content, status, now),
        )
        self.conn.commit()
        return cursor.lastrowid or 0

    def mark_invitation_sent(self, invitation_id: int) -> None:
        """标记邀约已发送"""
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE invitations SET status = 'sent', sent_at = ? WHERE id = ?",
            (now, invitation_id),
        )
        self.conn.commit()

    # ── 清理 ──────────────────────────────────────────────

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SessionStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
