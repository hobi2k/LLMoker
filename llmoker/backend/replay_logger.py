import json
import os
from datetime import datetime

from backend.sqlite_compat import sqlite


class ReplayLogger:
    """ReplayLogger, 라운드 결과를 SQLite 리플레이 로그로 저장한다.

    Args:
        db_path: 리플레이 SQLite 파일 경로.

    Returns:
        ReplayLogger: 리플레이 기록 객체.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_db()

    def _connect(self):
        """_connect, SQLite 연결을 생성한다.

        Args:
            없음.

        Returns:
            sqlite.Connection: SQLite 연결 객체.
        """

        return sqlite.connect(self.db_path)

    def _initialize_db(self):
        """_initialize_db, 리플레이 테이블을 초기화한다.

        Args:
            없음.

        Returns:
            None: 테이블을 생성한다.
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
        """append_round, 라운드 요약 정보를 리플레이 파일에 기록한다.

        Args:
            summary: 라운드 종료 요약 사전.

        Returns:
            None: 요약 정보를 SQLite 테이블에 추가한다.
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
