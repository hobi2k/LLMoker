import json
import os
from datetime import datetime

from backend.sqlite_compat import SQLITE_AVAILABLE, sqlite


class SaveStateStore:
    """
    SQLite에 세이브 슬롯을 저장하고 불러온다.
    Ren'Py 기본 세이브 대신 포커 매치 스냅샷만 따로 저장해 슬롯 정보를 단순하게 유지한다.

    Args:
        db_path: 세이브 SQLite 파일 경로다.
    """

    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_db()

    def _load_json_slots(self):
        if not os.path.isfile(self.db_path):
            return {}
        try:
            with open(self.db_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_json_slots(self, slot_map):
        with open(self.db_path, "w", encoding="utf-8") as handle:
            json.dump(slot_map, handle, ensure_ascii=False, indent=2)

    def _connect(self):
        """
        현재 세이브 데이터베이스 파일에 대한 새 SQLite 연결을 연다.
        짧은 트랜잭션 단위로 `with` 블록 안에서 바로 쓰도록 매 호출마다 새 연결을 만든다.

        Returns:
            현재 세이브 DB 연결 객체다.
        """

        if not SQLITE_AVAILABLE:
            raise RuntimeError("SQLite 드라이버를 사용할 수 없습니다.")
        return sqlite.connect(self.db_path)

    def _initialize_db(self):
        """
        세이브 슬롯 테이블이 아직 없으면 생성한다.
        앱 시작 시 여러 번 호출돼도 같은 스키마만 보장하고 추가 부작용은 만들지 않는다.
        """

        if not SQLITE_AVAILABLE:
            if not os.path.isfile(self.db_path):
                self._write_json_slots({})
            return

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

        저장은 슬롯 번호 기준 upsert로 처리해 같은 슬롯을 다시 저장하면 최신 내용으로 덮어쓴다.
        """

        payload = json.dumps(snapshot, ensure_ascii=False)
        updated_at = datetime.utcnow().isoformat()
        if not SQLITE_AVAILABLE:
            slot_map = self._load_json_slots()
            slot_map[str(slot)] = {
                "slot": slot,
                "label": label,
                "payload": snapshot,
                "updated_at": updated_at,
            }
            self._write_json_slots(slot_map)
            return

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

        if not SQLITE_AVAILABLE:
            slot_map = self._load_json_slots()
            entry = slot_map.get(str(slot))
            return None if not entry else entry.get("payload")

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
        화면 표시용 슬롯 목록을 고정 슬롯 수 기준으로 만든다.
        비어 있는 슬롯도 항상 함께 돌려줘 UI가 별도 보정 없이 1~3번 슬롯을 그대로 렌더링할 수 있게 한다.

        Returns:
            슬롯 정보 사전 목록이다.
        """

        slot_map = {slot: {"slot": slot, "label": "빈 슬롯", "updated_at": ""} for slot in range(1, 4)}
        if not SQLITE_AVAILABLE:
            stored = self._load_json_slots()
            for key, entry in stored.items():
                slot = int(key)
                slot_map[slot] = {
                    "slot": slot,
                    "label": entry.get("label", "빈 슬롯"),
                    "updated_at": entry.get("updated_at", ""),
                }
            return [slot_map[slot] for slot in sorted(slot_map)]

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
