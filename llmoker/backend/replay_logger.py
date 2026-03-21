import json
import os
from datetime import datetime

from backend.sqlite_compat import sqlite


class ReplayLogger:
    """
    라운드 결과를 나중에 다시 분석할 수 있도록 SQLite에 남긴다.

    Args:
        db_path: 리플레이 데이터베이스 파일 경로다.

    Returns:
        없음. 인스턴스를 초기화하고 저장소를 준비한다.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_db()

    def _connect(self):
        """
        현재 리플레이 데이터베이스에 대한 SQLite 연결을 연다.

        Args:
            없음.

        Returns:
            `sqlite3.Connection` 객체다.
        """

        return sqlite.connect(self.db_path)

    def _initialize_db(self):
        """
        리플레이 저장에 필요한 테이블이 없으면 만든다.

        Args:
            없음.

        Returns:
            없음. 데이터베이스 스키마만 보장한다.
        """

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS round_replay (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hand_no INTEGER NOT NULL,
                    winner TEXT NOT NULL,
                    pot INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def append_round(self, summary):
        """
        한 라운드가 끝난 뒤 핵심 요약 정보를 리플레이 로그에 추가한다.

        Args:
            summary: 우승자, 팟, 로그 등을 담은 라운드 요약 사전이다.

        Returns:
            없음. 요약 한 건을 데이터베이스에 저장한다.
        """

        payload = dict(summary)
        created_at = datetime.utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO round_replay (hand_no, winner, pot, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["hand_no"],
                    payload["winner"],
                    payload["pot"],
                    json.dumps(payload, ensure_ascii=False),
                    created_at,
                ),
            )
