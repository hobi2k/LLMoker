# 06. 증상별 감사 가이드

[목차로 돌아가기](README.md)

이 장은 “문제가 생겼을 때 어디부터 봐야 하는가”를 증상 기준으로 정리한다.

## 1. 대사 품질이 낮다

대표 증상:

- 프롬프트 문장을 비틀어 말함
- 없는 게임 용어를 지어냄
- 포커 테이블에서 할 법하지 않은 대사
- 내부 로그 냄새가 남

먼저 보는 순서:

1. `llmoker/backend/llm/prompts.py`
2. `llmoker/backend/llm/tasks.py`
3. `llmoker/backend/llm/runtime.py`
4. `llmoker/game/poker_dialogue.rpy`
5. `llmoker/backend/poker_engine.py`

이유:

- 프롬프트가 따라 말하기 쉽게 생겼을 수 있다.
- recent log를 날것으로 넘겼을 수 있다.
- 시스템 메시지와 프롬프트가 중복될 수 있다.
- 공개 로그가 내부 문자열로 오염됐을 수 있다.

## 2. 봇이 두 번 행동하는 것처럼 보인다

먼저 보는 순서:

1. `PokerMatch.resolve_player_action()`
2. `PokerMatch._run_bot_turns()`
3. `PokerMatch.resolve_draw_phase()`
4. 플레이어 행동 로그가 실제로 충분히 찍히는지

착시와 실제 버그를 분리해야 한다.

- 플레이어 로그가 빈약하면 봇만 두 번 움직인 것처럼 보일 수 있다.
- 액터 전환이 실제로 잘못되면 엔진 버그다.

## 3. 카드 교체 이유가 이상하다

대표 증상:

- 포커 외 다른 게임 용어 사용
- 뜬금없는 전략 이유
- 인덱스와 이유가 안 맞음

먼저 보는 순서:

1. `build_draw_prompt()`
2. `build_draw_task()`
3. `extract_draw_payload()`
4. `resolve_draw_phase()`

## 4. 새 게임인데 기억이 남는다

먼저 보는 순서:

1. `ensure_poker_runtime()`
2. `MemoryManager.clear_all()`
3. `PokerMatch.from_snapshot()`

핵심 질문:

- 지금이 새 게임 경로인가
- 세이브 복원 경로인가

## 5. 저장했는데 기억이 안 돌아온다

먼저 보는 순서:

1. `PokerMatch.to_snapshot()`
2. `PokerMatch.from_snapshot()`
3. `export_character_memory()`
4. `replace_character_memory()`

## 6. 액션 버튼이 이상하다

대표 증상:

- 폴드가 빠짐
- 폴드가 중복됨
- 체크/베팅이 이상한 타이밍에 뜸

먼저 보는 순서:

1. `_get_available_actions()`
2. `get_player_available_actions()`
3. `poker_table_screen(mode="betting")`

## 7. 결과 화면이 잘린다

먼저 보는 순서:

1. `poker_ui.rpy` 결과 패널
2. 카드 zoom
3. 라벨 글자 크기
4. 하단 버튼 배치

## 8. 메인 메뉴 품질이 떨어졌다

먼저 보는 순서:

1. 타이틀 가독성
2. 패널 폭
3. 메뉴 글자 크기
4. 배경 오버레이 세기

주요 파일:

- `screens.rpy`
- `gui.rpy`

## 9. 도움말, 정보, 환경 설정이 엔진 설명으로 가득하다

먼저 보는 순서:

1. `screens.rpy`
2. `gui.rpy`
3. `poker_ui.rpy`

핵심 질문:

- 사용자가 게임 조작을 보려는 화면에 Ren'Py 엔진 설명이 섞여 있지 않은가
- 정보와 환경 설정이 게임용 도움말을 넘어서 내부 구현 설명이 되어 있지 않은가
- 텍스트가 잘리는 이유가 화면 폭 문제인지, 내용 과밀 문제인지 분리되어 있는가

## 10. 로그 화면에서 게임으로 돌아갈 수 없다

먼저 보는 순서:

1. `poker_ui.rpy`
2. `screens.rpy`

핵심 질문:

- 로그 오버레이에 명시적 닫기 버튼이 있는가
- `Return` 또는 게임 복귀 액션이 실제로 연결되어 있는가
- 로그를 띄운 뒤 입력이 막히지 않는가

## 11. 런타임이 안 붙는다

현재는 stdin/stdout IPC 구조다.

먼저 보는 순서:

1. `5Drawminigame.sh`
2. `backend.llm.client`
3. `backend.llm.runtime`
4. 모델 경로와 Python 경로

핵심 질문:

- 외부 Python 3.11 런타임이 실제로 실행됐는가
- 모델 로드는 끝났는가
- tool context 초기화가 꼬이지 않았는가

## 12. 창이 안 떠도 먼저 확인할 수 있는가

먼저 보는 순서:

1. `llmoker/scripts/check_game_non_gui.sh`
2. `./5Drawminigame.sh . compile`
3. `./5Drawminigame.sh . lint`

이 경로로 먼저 잡아야 하는 문제:

- `.rpy` 문법 에러
- Ren'Py lint 경고
- 핵심 Python 파일 문법 에러

이 경로로는 못 잡는 문제:

- 컷신 전환 감각
- 메뉴와 HUD의 실제 겹침
- 카드 크기 체감
- 대사 품질

즉 자동 검증이 통과해도, GUI QA는 따로 해야 한다.

다음 장: [07. 파일별 코드 레퍼런스](07_file_reference.md)
