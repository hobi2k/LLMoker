import json
import os
from datetime import datetime

from backend.sqlite_compat import sqlite


class SaveStateStore:
    """
    SQLite에 세이브 슬롯을 저장하고 불러온다.

    Args:
        db_path: 세이브 SQLite 파일 경로다.

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
            현재 세이브 DB 연결 객체다.
        """

        return sqlite.connect(self.db_path)

    def _initialize_db(self):
        """
        세이브 슬롯 테이블을 초기화한다.

        Args:
            없음.

        Returns:
            없음.
        """

        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS save_state (
                    slot INTEGER PRIMARY KEY,
                    label TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save_slot(self, slot, label, snapshot):
        """
        지정 슬롯에 세이브 스냅샷을 저장한다.

        Args:
            slot: 저장할 슬롯 번호다.
            label: 화면 표시용 슬롯 이름이다.
            snapshot: 저장할 게임 상태 사전이다.

        Returns:
            없음.
        """

        payload = json.dumps(snapshot, ensure_ascii=False)
        updated_at = datetime.utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO save_state (slot, label, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slot) DO UPDATE SET
                    label=excluded.label,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (slot, label, payload, updated_at),
            )

    def load_slot(self, slot):
        """
        지정 슬롯의 세이브 스냅샷을 불러온다.

        Args:
            slot: 불러올 슬롯 번호다.

        Returns:
            스냅샷 사전 또는 None이다.
        """

        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM save_state WHERE slot = ?",
                (slot,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def list_slots(self):
        """
        화면 표시용 슬롯 목록을 반환한다.

        Args:
            없음.

        Returns:
            슬롯 정보 사전 목록이다.
        """

        slot_map = {slot: {"slot": slot, "label": "빈 슬롯", "updated_at": ""} for slot in range(1, 4)}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT slot, label, updated_at FROM save_state ORDER BY slot"
            ).fetchall()
        for slot, label, updated_at in rows:
            slot_map[slot] = {
                "slot": slot,
                "label": label,
                "updated_at": updated_at,
            }
        return [slot_map[slot] for slot in sorted(slot_map)]
