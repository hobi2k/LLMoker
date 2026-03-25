# 06. 증상별 감사 가이드

[목차로 돌아가기](README.md)

이 장은 “문제가 생겼을 때 어디부터 봐야 하는가”를 증상 기준으로 정리한다.

## 1. 시스템 나레이션이 헷갈린다

대표 증상:

- 누가 행동했는지 한눈에 안 보임
- `베팅`, `콜`, `레이즈` 표현이 뒤섞임
- 현재 단계와 다음 차례가 헷갈림
- 화면 문장과 엔진 실제 흐름이 다름

먼저 보는 순서:

1. `llmoker/backend/poker_engine.py`
   - 실제 행동 규칙과 턴 순서를 먼저 확인한다.
2. `llmoker/game/poker_dialogue.rpy`
   - `_action_summary_lines()`와 `_event_narration_lines()`가 엔진 로그를 어떤 문장으로 바꾸는지 확인한다.
3. `llmoker/game/screens.rpy`
   - 도움말의 진행 규칙과 화면 라벨이 실제 엔진과 같은지 확인한다.

핵심 원인:

- 엔진은 대칭인데 화면 문장이 비대칭으로 적힘
- `현재 테이블 베팅`과 `현재 콜 금액`이 혼동됨
- 행동 직후 설명이 없어서, 누가 무엇을 했는지 놓침

품질 검증: 실제 게임에서 한 라운드를 플레이하며 행동 나레이션과 도움말을 함께 대조한다.

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
- 인덱스와 이유가 안 맞음 — reason에 적힌 카드 이름이 실제 버린 카드와 다름
- 원페어 상태에서 페어를 이루는 카드 한 장을 버림

원인:

- `build_draw_prompt()`에 족보별 교체 규칙이 없으면 모델이 임의로 인덱스를 고른다.
- 원페어의 경우 "두 장 모두 유지, 나머지에서 버린다"는 규칙이 명시되어야 한다.
- reason은 실제로 버리는 카드 이름과 유지하는 족보 이름을 명시하도록 요구해야 한다.

먼저 보는 순서:

1. `build_draw_prompt()` — 족보별 교체 규칙이 있는지 확인
2. `build_draw_task()` — 손패 인덱스와 카드 이름이 올바르게 전달되는지 확인
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

## 11. LLM 오류 화면에서 게임이 죽는다

대표 증상:

- `Exception: Open text tag at end of string` — Ren'Py 대화창이 오류 메시지를 표시하다 죽음
- LLM 출력 미리보기가 포함된 오류 메시지에서 재현됨
- `LLM NPC 행동 선택 실패: LLM이 허용되지 않은 행동을 반환했습니다. 출력 미리보기: {"action": ...}` — 오류 발생 후 검은 화면

원인:

- LLM 오류 메시지에 포함된 JSON 미리보기(`{"action": ...}`)의 `{`를 Ren'Py가 텍스트 태그 시작으로 해석한다.
- `store.poker_fatal_error_text`에 저장하기 전에 `{` → `{{`, `}` → `}}`로 이스케이프해야 한다.
- **JSON 출력 잘림 버그**: `max_new_tokens: 64`가 너무 작아 한국어 reason 텍스트가 토큰 한계에 걸려 JSON이 불완전하게 잘린다. `extract_json_payload`가 파싱에 실패하고 `action` 검증 오류로 이어진다. `max_new_tokens: 128`로 설정해야 한다.

먼저 보는 순서:

1. `llmoker/game/poker_core.rpy` — `safe_resolve_player_action()`, `safe_resolve_draw_phase()` 내 이스케이프 처리 확인
2. `llmoker/game/poker_minigame.rpy` — `poker_runtime_error` 레이블 확인
3. `llmoker/backend/llm/tasks.py` — `build_action_task()`, `build_draw_task()` 내 `max_new_tokens` 값 확인 (128 이상이어야 함)

## 12. 대사 tool calling이 `'NoneType' object has no attribute 'get'`으로 항상 실패한다

대표 증상:

- 모든 dialogue 이벤트에서 `사야 대사 생성 실패 / 이유: 'NoneType' object has no attribute 'get'`
- action/draw/policy는 정상 동작
- `data/logs/qwen_runtime.log`에서 traceback이 `qwen_agent/agent.py` line 124로 끝남

원인:

- qwen-agent 0.0.34 `FnCallAgent._run()` 내부에서 도구 호출 결과 메시지를 만들 때
  `extra={'function_id': out.extra.get('function_id', '1')}`를 실행한다.
- 로컬 transformers 모델이 반환한 Message의 `extra` 필드가 None이면
  `AttributeError: 'NoneType' object has no attribute 'get'`가 발생한다.

먼저 보는 순서:

1. `data/logs/qwen_runtime.log` — traceback 전체 확인
2. `backend/llm/runtime.py` — 메시지 파싱 함수가 `None`과 `extra=None`을 방어하는지 확인
3. `load_model()` — 대사 경로가 직접 생성(`run_chat`) 기준으로 초기화됐는지 확인

수정 방법:

- `backend/llm/runtime.py`의 메시지 순회 함수와 대사 선택 파서를 먼저 점검한다.
- `messages` 목록 안에 `None`이 섞여도 건너뛰게 유지한다.
- 대사 경로는 직접 생성 결과를 쓰므로, 후처리가 `None` 메시지나 설명투 출력에 의존하지 않게 한다.

## 13. 런타임이 안 붙는다

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
