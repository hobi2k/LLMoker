# LLM NPC 설정 문서

## 현재 범위

현재 LLM NPC는 아래 세 가지만 맡는다.

- 행동 선택
- 카드 교체 판단
- 라운드 회고를 반영한 다음 행동 적응

화면에 보이는 문장은 LLM 대사가 아니라 시스템 나레이션이다.

## 구조

1. `backend/poker_engine.py`
   - 포커 규칙, 턴 순서, 공개/비공개 정보 경계를 관리한다.
2. `backend/llm/agent.py`
   - 엔진이 호출하는 상위 어댑터다.
3. `backend/llm/tasks.py`
   - 행동, 교체 태스크 payload를 만든다.
4. `backend/llm/prompts.py`
   - 행동, 교체 프롬프트를 만든다.
5. `backend/llm/client.py`
   - Ren'Py와 Python 3.11 런타임 사이 IPC를 관리한다.
6. `backend/llm/runtime.py`
   - transformers 모델과 Qwen-Agent `FnCallAgent`를 실제로 실행한다.
7. `game/poker_dialogue.rpy`
   - 대사 대신 행동/단계 나레이션만 출력한다.
8. `backend/policy_loop.py`
   - 라운드가 끝난 뒤 한 번만 LLM 회고를 생성한다.
   - 공개 사실과 어긋나는 회고는 저장하지 않는다.

## 실행 방식

- 기본 모델: `llmoker/models/llm/qwen3-4b-instruct-2507`
- 기본 런타임: `Qwen-Agent + transformers + stdin/stdout IPC`
- 예열 시점: 프로그램 시작 직후 `label splashscreen`
- 실제 게임에서 첫 행동 판단 전까지 런타임이 이미 떠 있는 상태를 목표로 한다.

## 정보 공개 원칙

LLM NPC는 아래 공개 정보만 본다.

- 자기 손패
- 현재 족보
- 현재 팟
- 양측 스택
- 현재 테이블 베팅
- 현재 콜 금액
- 허용 행동
- 공개 로그
- 최근 전략 피드백
- 장기 전략 기억

보면 안 되는 정보:

- 플레이어 손패
- 플레이어 드로우 후 실제 카드 구성

## 출력 원칙

- 행동은 합법 행동 하나만 고른다.
- 카드 교체는 인덱스 목록만 고른다.
- 회고는 LLM이 `result`, `ending`, `pressure`, `bot_hand_bucket`, `adjustment`, `strategy_focus` 슬롯을 고르고, 코드가 `short_term`, `long_term`, `strategy_focus` 문장으로 변환한다.
- 다만 승패, 족보, 폴드 종료 여부와 충돌하는 회고는 저장하지 않는다.
- 행동과 카드 교체는 최근 전략 피드백과 장기 전략 기억을 함께 참고한다.
- 대사 생성은 현재 비활성이다.
- 게임 화면 문장은 `플레이어는 체크했다`, `사야는 10칩 베팅했다` 같은 시스템 나레이션만 사용한다.

## 규칙 메모

- 베팅이 없는 상태에서는 합법 행동이 `check`, `bet`만 뜬다.
- `fold`는 콜 금액이 생긴 뒤에만 합법 행동으로 들어간다.
- 정책 회고는 라운드 중간에 생성되지 않고, `폴드 종료` 또는 `쇼다운 결과`가 확정된 뒤 한 번만 저장을 시도한다.
