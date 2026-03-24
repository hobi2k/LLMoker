# 04. 기억, 회고, 세이브

[목차로 돌아가기](README.md)

이 장은 **기억이 언제 생기고, 언제 사라지고, 저장과 복원이 어떻게 엮이는지** 설명한다.

## 1. 왜 기억 계층이 따로 있나

이 게임은 단순 포커 엔진만 있는 게 아니다.  
LLM NPC가 이전 판을 바탕으로 다음 판단을 바꿀 수 있도록 기억 계층이 존재한다.

즉 기억은:

- 행동 이유
- 대사 톤
- 카드 교체 성향
- 다음 전략 초점

에 영향을 줄 수 있다.

## 2. 현재 원하는 기억 규칙

이 프로젝트에서 현재 맞는 규칙은 아래다.

- 새 게임 시작: 기억 초기화
- 저장: 현재 매치 상태와 기억을 함께 저장
- 불러오기: 저장 당시 기억을 함께 복원
- 저장 안 하고 종료: 기억은 이어지지 않음

이 규칙을 어기면 플레이어는 바로 이상함을 느낀다.

## 3. `memory_manager.py`

### `MemoryManager`

역할:

- SQLite에 단기/장기 기억을 저장하고 읽는다.

### `append_feedback(character_name, text, metadata=None, long_term=False)`

기능:

- 새 회고 문장을 기억 DB에 추가

입력:

- 캐릭터 이름
- 회고 텍스트
- 메타데이터
- 장기 기억 여부

출력:

- 없음

### `get_recent_feedback(character_name, limit=5, long_term=False)`

기능:

- 최근 기억 조회

입력:

- 캐릭터 이름
- 개수 제한
- 장기 기억 여부

출력:

- 기억 항목 사전 목록

### `clear_all()`

기능:

- 기억 전체 삭제

의미:

- 새 게임 시작 시 이 함수가 반드시 타야 한다.

### `export_character_memory(character_name)`

기능:

- 세이브용 기억 스냅샷 생성

출력:

- `short_term`, `long_term` 키를 가진 사전

### `replace_character_memory(character_name, memory_snapshot)`

기능:

- 저장된 기억 스냅샷으로 현재 기억을 완전히 교체

의미:

- 불러오기 시 이 함수가 반드시 타야 한다.

## 4. `policy_loop.py`

### `PolicyLoop`

역할:

- 라운드 종료 후 회고를 만들고 메모리에 저장할지 결정

### `_build_rule_feedback(round_summary)`

기능:

- LLM이 없을 때 쓰는 규칙 기반 회고 생성

### `build_feedback(round_summary, public_log, bot_mode)`

기능:

- 봇 모드에 따라 회고 생성

입력:

- 라운드 요약
- 공개 로그
- 봇 모드

출력:

- 정책 피드백 사전

핵심 포인트:

- LLM 회고가 실패하면 그 실패를 명시적으로 남긴다.
- 실패한 회고는 저장하면 안 된다.

### `persist_feedback(round_summary, public_log, bot_mode)`

기능:

- 성공한 회고만 메모리에 저장

입력:

- 라운드 요약
- 공개 로그
- 봇 모드

출력:

- 저장 결과 피드백 사전

위험:

- 품질이 낮은 회고가 계속 저장되면 다음 판단 전체를 오염시킨다.

## 5. `save_state_store.py`

### `SaveStateStore`

역할:

- SQLite 기반 세이브 슬롯 관리

### `save_slot(slot, label, snapshot)`

기능:

- 지정 슬롯에 스냅샷 저장

### `load_slot(slot)`

기능:

- 지정 슬롯에서 스냅샷 복원

### `list_slots()`

기능:

- 화면 표시용 슬롯 목록 반환

## 6. 기억과 저장이 실제로 만나는 지점

실제 연결은 `poker_core.rpy`와 `poker_engine.py`에서 일어난다.

### 새 게임

`ensure_poker_runtime()` 안에서:

- 세이브 스냅샷이 없으면 `MemoryManager.clear_all()`
- 그 뒤 새 `PokerMatch`

### 저장

`PokerMatch.to_snapshot()` 안에서:

- 현재 매치 상태
- 현재 기억 스냅샷

을 함께 저장

### 불러오기

`PokerMatch.from_snapshot()` 안에서:

- 매치 상태 복원
- `replace_character_memory()` 호출

## 7. 감사 포인트

### 새 게임인데 기억이 남는다

먼저 볼 것:

- `ensure_poker_runtime()` 새 게임 경로
- `MemoryManager.clear_all()`

### 저장했는데 기억이 안 돌아온다

먼저 볼 것:

- `PokerMatch.to_snapshot()`
- `PokerMatch.from_snapshot()`
- `replace_character_memory()`

### 행동과 대사가 계속 같은 방식으로 굳는다

먼저 볼 것:

- 회고 품질
- `persist_feedback()` 저장 조건
- 최근 기억 조회 결과

다음 장: [05. Ren'Py UI와 화면 구성](05_renpy_ui.md)
