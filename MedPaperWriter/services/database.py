"""
数据库模块
使用 SQLite 提供可靠的数据持久化
"""

import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config.settings import settings
from services.logger import logger


class Database:
    """SQLite 数据库管理器 - 线程安全"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        db_dir = settings.BASE_DIR / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_dir / "medtoolkit.db"

        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 会话表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_token TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'in_progress',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)

        # 会话索引（用于快速查询）
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_status 
            ON sessions(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_mode 
            ON sessions(mode)
        """)

        # Token 使用记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        # 导出记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                export_time TEXT NOT NULL,
                language TEXT NOT NULL,
                ref_style TEXT NOT NULL,
                file_path TEXT,
                status TEXT NOT NULL DEFAULT 'completed',
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        conn.commit()
        logger.info("Database initialized", db_path=str(self.db_path))

    # === 会话操作 ===

    def save_session(self, session_id: str, user_token: str, mode: str, data: dict):
        """保存或更新会话"""
        conn = self._get_connection()
        now = datetime.now().isoformat()
        data_json = json.dumps(data, ensure_ascii=False)

        conn.execute("""
            INSERT INTO sessions (session_id, user_token, mode, status, created_at, updated_at, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                status = excluded.status,
                updated_at = excluded.updated_at,
                data = excluded.data
        """, (
            session_id,
            user_token,
            mode,
            data.get("status", "in_progress"),
            data.get("created_at", now),
            now,
            data_json
        ))
        conn.commit()

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话数据"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT data FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["data"])
        return None

    def get_session_meta(self, session_id: str) -> Optional[dict]:
        """获取会话元数据（不含完整 data）"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT session_id, user_token, mode, status, created_at, updated_at FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def list_sessions(self, limit: int = 20, offset: int = 0) -> List[dict]:
        """列出最近的会话"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT session_id, mode, status, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    # === Token 记录 ===

    def record_token_usage(self, session_id: str, prompt_tokens: int, completion_tokens: int):
        """记录 Token 使用"""
        conn = self._get_connection()
        total = prompt_tokens + completion_tokens
        conn.execute("""
            INSERT INTO token_usage (session_id, timestamp, prompt_tokens, completion_tokens, total_tokens)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, datetime.now().isoformat(), prompt_tokens, completion_tokens, total))
        conn.commit()

    def get_token_usage(self, session_id: str) -> dict:
        """获取会话的 Token 使用统计"""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as call_count,
                COALESCE(SUM(prompt_tokens), 0) as total_prompt,
                COALESCE(SUM(completion_tokens), 0) as total_completion,
                COALESCE(SUM(total_tokens), 0) as total_tokens
            FROM token_usage 
            WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else {
            "call_count": 0,
            "total_prompt": 0,
            "total_completion": 0,
            "total_tokens": 0
        }

    # === 导出记录 ===

    def record_export(self, session_id: str, language: str, ref_style: str, file_path: str = ""):
        """记录导出"""
        conn = self._get_connection()
        conn.execute("""
            INSERT INTO exports (session_id, export_time, language, ref_style, file_path)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, datetime.now().isoformat(), language, ref_style, file_path))
        conn.commit()

    def get_export_history(self, session_id: str) -> List[dict]:
        """获取导出历史"""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT * FROM exports WHERE session_id = ? ORDER BY export_time DESC",
            (session_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # === 维护操作 ===

    def vacuum(self):
        """压缩数据库"""
        conn = self._get_connection()
        conn.execute("VACUUM")
        logger.info("Database vacuum completed")

    def get_stats(self) -> dict:
        """获取数据库统计信息"""
        conn = self._get_connection()
        stats = {}

        cursor = conn.execute("SELECT COUNT(*) as count FROM sessions")
        stats["total_sessions"] = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM token_usage")
        stats["total_api_calls"] = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM exports")
        stats["total_exports"] = cursor.fetchone()["count"]

        cursor = conn.execute("""
            SELECT COALESCE(SUM(total_tokens), 0) as total 
            FROM token_usage
        """)
        stats["total_tokens_used"] = cursor.fetchone()["total"]

        return stats


# 全局数据库实例
db = Database()
