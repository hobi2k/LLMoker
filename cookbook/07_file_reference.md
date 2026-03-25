# 07. 파일별 코드 레퍼런스

[목차로 돌아가기](README.md)

이 장은 앞선 장들이 `개념`과 `흐름` 중심이었다면,  
실제 수정할 때 바로 열어볼 수 있게 **파일별 핵심 함수와 역할을 정리한 색인**이다.

이 장은 앞 장을 대체하지 않는다.  
앞 장을 읽고 난 뒤 실제 편집 위치를 찾는 용도다.

## 1. 런처와 Ren'Py

### `llmoker/5Drawminigame.sh`

- 역할: 실행 진입점, bootstrap, 런타임 정리
- 먼저 볼 때: 시작 지연, 종료 후 프로세스 잔류

### `llmoker/game/script.rpy`

- `label splashscreen`
  - 프로그램 시작 직후 로고 영상, 인트로 영상, 오프닝 영상을 순서대로 재생한다.
  - 이 구간에서 백그라운드 예열도 함께 시작한다.
- `begin_llm_npc_prewarm()`
  - 스플래시 시퀀스 동안 외부 런타임 예열을 백그라운드로 시작한다.
- `label start`
  - 백그라운드 예열 결과를 이어받는다.
  - 남은 초기화가 있으면 마무리한 뒤 `poker_minigame`으로 이동한다.
- 먼저 볼 때:
  - 프로그램 시작 시 지연
  - 인트로 재생 순서
  - 예열 시점 변경
  - 게임 진입 전에 런타임을 준비해야 하는 요구

### `llmoker/game/poker_minigame.rpy`

- `label poker_minigame`
  - 게임 시작
- `label poker_phase_loop`
  - 페이즈 루프
- `label poker_round_end`
  - 결과 화면
- `label after_load`
  - 복원 후 처리

### `llmoker/game/poker_core.rpy`

- `ensure_poker_runtime()`
  - 백엔드 객체 준비
- `get_poker_match()`
  - 현재 매치 반환
- `sync_poker_match_state()`
  - 세이브 가능한 스냅샷 동기화
- `save_poker_slot()`
  - 슬롯 저장
- `load_poker_slot()`
  - 슬롯 로드
- `start_round()`
  - 새 라운드 시작
- `start_llm_npc()`
  - LLM 런타임 준비
- `safe_resolve_player_action()`
  - 플레이어 행동 적용 래퍼
- `safe_resolve_draw_phase()`
  - 드로우 적용 래퍼

### `llmoker/game/poker_dialogue.rpy`

- `_escape_renpy_say_text()`
  - Ren'Py 치환 문자 이스케이프
- `_action_summary_lines()`
  - 행동 로그를 화면용 나레이션으로 정리
- `_event_narration_lines()`
  - 단계/결과 시스템 나레이션 생성
- `play_dialogue_event()`
  - 실제 나레이션 출력

## 2. 포커 엔진

### `llmoker/backend/poker_engine.py`

#### 클래스

- `PlayerState`
- `PokerMatch`

#### 라운드와 상태

- `start_new_round()`
- `phase_name_ko()`
- `can_continue_match()`
- `is_match_finished()`

#### 손패와 정보 조회

- `get_player_hand()`
- `get_bot_hand()`
- `get_player_hand_name()`
- `get_bot_hand_name()`
- `get_public_log_lines()`
- `get_recent_log_text()`

#### 행동 계산

- `_get_available_actions()`
- `get_player_available_actions()`
- `get_player_amount_to_call()`
- `get_bot_amount_to_call()`
- `can_player_raise()`
- `get_raise_total_amount()`
- `get_betting_status_text()`

#### 행동 적용

- `resolve_player_action()`
- `_apply_betting_action()`
- `_run_bot_turns()`
- `_advance_after_betting()`
- `_finish_by_fold()`

#### 드로우

- `resolve_draw_phase()`

#### 결과와 세이브

- `_finalize_round_summary()`
- `_resolve_showdown()`
- `to_snapshot()`
- `from_snapshot()`

## 3. 기억과 저장

### `llmoker/backend/memory_manager.py`

- `append_feedback()`
- `get_recent_feedback()`
- `export_character_memory()`
- `clear_all()`
- `replace_character_memory()`

### `llmoker/backend/policy_loop.py`

- `_build_rule_feedback()`
- `build_feedback()`
- `persist_feedback()`

### `llmoker/backend/save_state_store.py`

- `save_slot()`
- `load_slot()`
- `list_slots()`

## 4. LLM 백엔드

### `llmoker/backend/llm/agent.py`

- `LocalLLMAgent.__init__()`
- `reconfigure()`
- `start()`
- `stop()`
- `choose_action()`
- `choose_discards()`
- `generate_policy_feedback()`

### `llmoker/backend/llm/client.py`

- `QwenRuntimeClient.configure()`
- `QwenRuntimeClient.start()`
- `QwenRuntimeClient.stop()`
- `QwenRuntimeClient.request()`
- `main()`

### `llmoker/backend/llm/runtime.py`

#### 출력 정리 helper

- `preview_text()`
- `looks_like_meta_response()`
- `normalize_reason_text()`
- `extract_json_payload()`
- `extract_action_payload()`
- `extract_draw_payload()`

#### 시스템 메시지

- `build_decision_system_message()`
- `build_policy_system_message()`

#### 메시지/모델 계층

- `message_text()`
- `final_assistant_text()`
- `LocalTransformersFnCallModel`
- `QwenRuntime`

#### IPC

- `write_ipc_payload()`
- `serve_ipc()`
- `main()`

### `llmoker/backend/llm/prompts.py`

- `build_public_state_text()`
- `build_action_prompt()`
- `build_draw_prompt()`
- `build_policy_feedback_prompt()`

### `llmoker/backend/llm/tasks.py`

- `PokerAgentTask`
- `build_decision_context()`
  - 행동과 카드 교체가 쓰는 공개 상태 중심 결정용 문맥 생성기
- `build_action_task()`
- `build_draw_task()`
- `build_policy_task()`

### `llmoker/backend/llm/tools.py`

- `set_tool_context()`
- `clear_tool_context()`
- `GetPublicStateTool`
- `GetMemoryTool`
- `GetRecentLogTool`
- `GetRoundSummaryTool`
- `build_poker_tools()`

## 5. UI 파일

### `llmoker/game/gui.rpy`

- 공통 스케일
- 대화창 높이
- 이름표 위치와 크기

### `llmoker/game/screens.rpy`

- `screen say`
- `screen navigation`
- `screen main_menu`
- `screen game_menu`
- `screen preferences`

### `llmoker/game/poker_ui.rpy`

- `get_poker_table_background_name()`
- `get_poker_dialogue_background_name()`
- `screen poker_dialogue_backdrop`
- `screen poker_save_overlay`
- `screen poker_load_overlay`
- `screen poker_log_overlay`
- `screen poker_settings_overlay`
- `screen poker_table_screen`

## 6. 이 장을 어떻게 쓰는가

앞선 장에서 구조와 원인을 이해한 뒤,  
실제 수정 위치를 찾을 때 이 장을 쓴다.

예:

- 대사 품질 문제
  - 03장 읽기
  - 여기서 `prompts.py`, `tasks.py`, `runtime.py` 항목으로 이동
- 카드 크기와 HUD 가독성 문제
  - 05장 읽기
  - 여기서 `poker_ui.rpy`, `gui.rpy` 항목으로 이동
- 기억이 저장/복원과 다르게 움직이는 문제
  - 04장 읽기
  - 여기서 `memory_manager.py`, `poker_core.rpy`, `poker_engine.py` 항목으로 이동
