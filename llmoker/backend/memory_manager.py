import json
import os
from datetime import datetime

from backend.sqlite_compat import sqlite


class MemoryManager:
    """
    NPC의 단기/장기 기억을 SQLite로 관리한다.
    정책 회고를 scope별로 분리해 저장하고, 다음 프롬프트에서 필요한 범위만 다시 읽어오게 만든다.

    Args:
        db_path: 기억 SQLite 파일 경로다.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_db()

    def _connect(self):
        """
        현재 기억 데이터베이스 파일에 대한 새 SQLite 연결을 연다.
        메모리 읽기와 쓰기가 모두 짧은 쿼리라 연결 풀 대신 매번 열고 닫는 방식을 유지한다.

        Returns:
            현재 기억 DB 연결 객체다.
        """

        return sqlite.connect(self.db_path)

    def _initialize_db(self):
        """
        기억 저장 테이블이 없으면 만든다.
        스키마 보장만 담당하며, 이미 테이블이 있을 때는 데이터에 손대지 않는다.
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

        단기 기억과 장기 기억은 `memory_scope` 컬럼으로만 구분해, 검색 경로는 단순하게 유지한다.
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

    def _fetch_feedback_rows(self, character_name, long_term=False):
        """
        특정 캐릭터의 기억 행을 생성 순서대로 모두 읽는다.

        Args:
            character_name: 기억을 읽을 캐릭터 이름이다.
            long_term: 장기 기억 조회 여부다.

        Returns:
            기억 행 사전 목록이다.
        """

        memory_scope = "long_term" if long_term else "short_term"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT text, metadata, created_at
                FROM memory_entry
                WHERE character_name = ? AND memory_scope = ?
                ORDER BY id ASC
                """,
                (character_name, memory_scope),
            ).fetchall()

        return [
            {
                "character": character_name,
                "text": text,
                "timestamp": created_at,
                "metadata": json.loads(metadata or "{}"),
            }
            for text, metadata, created_at in rows
        ]

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

        rows = self._fetch_feedback_rows(character_name, long_term=long_term)
        if limit <= 0:
            return rows
        return rows[-limit:]

    def export_character_memory(self, character_name):
        """
        한 캐릭터의 단기/장기 기억 전체를 스냅샷용 사전으로 만든다.

        Args:
            character_name: 내보낼 캐릭터 이름이다.

        Returns:
            세이브 스냅샷에 넣을 기억 사전이다.
        """

        return {
            "short_term": self._fetch_feedback_rows(character_name, long_term=False),
            "long_term": self._fetch_feedback_rows(character_name, long_term=True),
        }

    def clear_all(self):
        """
        기억 테이블 전체를 비운다.
        저장을 불러오지 않고 새 게임을 시작할 때 이전 세션 기억이 남지 않게 하는 용도다.
        """

        with self._connect() as connection:
            connection.execute("DELETE FROM memory_entry")

    def replace_character_memory(self, character_name, memory_snapshot):
        """
        한 캐릭터의 기억을 스냅샷 내용으로 통째로 갈아낀다.

        Args:
            character_name: 복원할 캐릭터 이름이다.
            memory_snapshot: `short_term`, `long_term` 목록을 담은 사전이다.
        """

        short_term_items = list((memory_snapshot or {}).get("short_term", []))
        long_term_items = list((memory_snapshot or {}).get("long_term", []))

        with self._connect() as connection:
            connection.execute("DELETE FROM memory_entry WHERE character_name = ?", (character_name,))
            for item in short_term_items:
                connection.execute(
                    """
                    INSERT INTO memory_entry (character_name, memory_scope, text, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        character_name,
                        "short_term",
                        item.get("text", ""),
                        json.dumps(item.get("metadata", {}), ensure_ascii=False),
                        item.get("timestamp") or datetime.utcnow().isoformat(),
                    ),
                )
            for item in long_term_items:
                connection.execute(
                    """
                    INSERT INTO memory_entry (character_name, memory_scope, text, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        character_name,
                        "long_term",
                        item.get("text", ""),
                        json.dumps(item.get("metadata", {}), ensure_ascii=False),
                        item.get("timestamp") or datetime.utcnow().isoformat(),
                    ),
                )
