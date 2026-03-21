import json
import os
from datetime import datetime

from backend.sqlite_compat import sqlite


class MemoryManager:
    """
    NPC의 단기/장기 기억을 SQLite로 관리한다.

    Args:
        db_path: 기억 SQLite 파일 경로다.

    Returns:
        없음.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_db()

    def _connect(self):
        """
        SQLite 연결을 생성한다.

        Args:
            없음.

        Returns:
            현재 기억 DB 연결 객체다.
        """

        return sqlite.connect(self.db_path)

    def _initialize_db(self):
        """
        기억 저장 테이블을 초기화한다.

        Args:
            없음.

        Returns:
            없음.
        """

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_name TEXT NOT NULL,
                    memory_scope TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def append_feedback(self, character_name, text, metadata=None, long_term=False):
        """
        캐릭터 기억 테이블에 새 피드백을 추가한다.

        Args:
            character_name: 기억을 남길 캐릭터 이름이다.
            text: 저장할 회고 문장이다.
            metadata: 함께 저장할 부가 정보 사전이다.
            long_term: 장기 기억 여부다.

        Returns:
            없음.
        """

        memory_scope = "long_term" if long_term else "short_term"
        created_at = datetime.utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_entry (character_name, memory_scope, text, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    character_name,
                    memory_scope,
                    text,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    created_at,
                ),
            )

    def get_recent_feedback(self, character_name, limit=5, long_term=False):
        """
        최근 기억 항목을 SQLite에서 조회한다.

        Args:
            character_name: 기억을 읽을 캐릭터 이름이다.
            limit: 최대 조회 개수다.
            long_term: 장기 기억 조회 여부다.

        Returns:
            최근 기억 항목 사전 목록이다.
        """

        memory_scope = "long_term" if long_term else "short_term"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT text, metadata, created_at
                FROM memory_entry
                WHERE character_name = ? AND memory_scope = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (character_name, memory_scope, limit),
            ).fetchall()

        return [
            {
                "character": character_name,
                "text": text,
                "timestamp": created_at,
                "metadata": json.loads(metadata or "{}"),
            }
            for text, metadata, created_at in reversed(rows)
        ]
