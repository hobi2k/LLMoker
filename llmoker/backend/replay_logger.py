import json
import os
from datetime import datetime

from backend.sqlite_compat import sqlite


class ReplayLogger:
    """
    라운드 결과를 나중에 다시 분석할 수 있도록 SQLite에 남긴다.
    포커 엔진은 여기만 호출하고, 실제 직렬화 형식과 저장 스키마는 이 클래스 안에 가둔다.

    Args:
        db_path: 리플레이 데이터베이스 파일 경로다.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_db()

    def _connect(self):
        """
        현재 리플레이 데이터베이스 파일에 대한 새 SQLite 연결을 연다.
        리플레이는 쓰기 위주라 연결을 오래 쥐지 않고 필요할 때마다 짧게 열고 닫는다.

        Returns:
            `sqlite3.Connection` 객체다.
        """

        return sqlite.connect(self.db_path)

    def _initialize_db(self):
        """
        리플레이 저장용 테이블이 없을 때만 생성한다.
        런타임 초기화 시 안전하게 여러 번 호출될 수 있도록 idempotent하게 유지한다.
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

        저장 시점의 UTC 시간도 함께 남겨 나중에 라운드 흐름을 시간순으로 다시 살펴볼 수 있게 한다.
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
