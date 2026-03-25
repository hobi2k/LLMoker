# 03. LLM 백엔드와 Qwen-Agent

[목차로 돌아가기](README.md)

이 장은 **LLMoker의 현재 활성 LLM 구조**를 설명한다.  
핵심은 `Qwen-Agent가 지금의 기반`이라는 점이다.  
이 장은 “에이전트를 얹는” 구조가 아니라, 에이전트 중심으로 어떻게 판단이 조립되는지 보는 장이다.

정리하면, `transformers`는 실제 추론 엔진이고 `Qwen-Agent`는 행동, 카드 교체, 회고를 묶는 기본 오케스트레이션 계층이다.

## 1. 전체 구조

현재 활성 경로:

- `agent.py`
- `client.py`
- `runtime.py`
- `tasks.py`
- `prompts.py`
- `tools.py`

실제 흐름:

1. 엔진이 “행동/카드 교체/회고가 필요하다”고 판단한다.
2. `LocalLLMAgent`가 현재 상황을 task로 만든다.
3. `QwenRuntimeClient`가 외부 Python 3.11 런타임에 요청한다.
4. `runtime.py`가 `Qwen-Agent + transformers`로 결과를 만든다.
5. 라운드 종료 뒤 `policy_loop.py`가 공개 로그와 종료 결과를 바탕으로 LLM 회고를 한 번만 요청한다.
6. 결과를 다시 엔진이 검증하고 적용한다.

검증 스크립트:

- `llmoker/scripts/verify_llm_policy_simulation.py`
  - 실제 포커 엔진과 실제 Qwen 런타임으로 3판 이상을 자동 진행한다.
  - 라운드 종료 전에는 `latest_feedback`가 비어 있어야 하고, 라운드 종료 뒤에만 회고가 생기는지 확인한다.
  - 회고 문장이 승패, 종료 방식, 족보와 충돌하지 않는지도 함께 본다.

중요한 점:

- 이 런타임은 첫 행동 판단 때 늦게 띄우지 않는다.
- `game/script.rpy`의 `label splashscreen`이 인트로와 오프닝 시퀀스를 재생하는 동안 백그라운드 예열을 시작한다.
- `label start`는 그 예열 결과를 이어받고, `poker_minigame`에 들어간 뒤에는 이미 떠 있는 런타임을 재사용하는 구조다.

## 2. `agent.py`

### `LocalLLMAgent`

이 클래스는 포커 엔진이 LLM을 사용할 때 보는 유일한 창구다.

주요 책임:

- 런타임 시작/중지
- 메모리 읽기
- task 생성
- runtime 요청
- 결과 정규화

### `__init__(local_model_path, llm_model_name, llm_runtime_python, llm_device, memory_manager)`

기능:

- `QwenRuntimeClient`를 만든다.
- 기억 관리자 핸들을 들고 있다.

입력:

- 모델 경로
- 모델 이름
- 외부 Python 경로
- 디바이스 힌트
- 기억 관리자

출력:

- 없음

### `start()`

기능:

- 외부 런타임을 미리 시작한다.

입력:

- 없음

출력:

- 준비 성공 여부 `bool`

의미:

프로그램 시작 직후 스플래시 시퀀스 동안 런타임을 미리 올려 두고, 첫 행동에서 느껴지는 지연을 줄이기 위해 사용된다.

### `choose_action(match, legal_actions)`

기능:

- 현재 턴의 행동을 요청한다.

입력:

- 현재 매치
- 허용 행동 목록

출력:

- `{status, action, reason}` 형태 결과

추가 검증:

- action이 합법 행동 목록에 실제로 포함되는지 검사한다.

### `choose_discards(match, max_discards)`

기능:

- 카드 교체 인덱스를 요청하고 정리한다.

입력:

- 현재 매치
- 최대 교체 장수

출력:

- `{status, discard_indexes, reason}`

추가 검증:

- 인덱스가 0~4 사이인지
- 중복이 없는지
- 최대 교체 장수를 넘지 않는지

## 3. `tasks.py`

이 파일은 **무슨 정보를 런타임으로 넘길지 결정하는 층**이다.  
프롬프트 품질이 흔들리는 원인은 종종 모델보다 여기서 넘어가는 문맥 구성이 더 크다.

### `PokerAgentTask`

역할:

- 하나의 LLM 요청 단위를 표현한다.

주요 필드:

- `task_type`
- `system_message`
- `prompt`
- `context`
- `max_tokens`

### `build_decision_context(match, legal_actions)`

기능:

- 행동/카드 교체처럼 판단 중심 task에 쓸 경량 컨텍스트를 만든다.

입력:

- 매치
- 허용 행동

출력:

- 결정용 컨텍스트 사전

중요:

- 행동과 카드 교체는 최근 전략 피드백과 장기 기억을 함께 읽는다.
- 다만 전체 메모리를 다 넣지 않고, 최근 단기 몇 개와 장기 몇 개만 제한해서 넣는다.
- 현재 활성 경로에서 행동과 카드 교체는 이 컨텍스트를 공통으로 사용한다.

### `build_action_task(...)`

기능:

- 행동 선택용 task 생성

입력:

- 매치
- 허용 행동

출력:

- `PokerAgentTask`

중요:

- 행동 task는 캐릭터성보다 합법성과 형식 안정성이 중요하다.
- 내부적으로 `build_decision_context()`를 사용한다.
- 현재 출력 상한은 `64` 토큰이다.

### `build_draw_task(...)`

기능:

- 카드 교체 판단용 task 생성

출력:

- `PokerAgentTask`

중요:

- 여기 입력이 잘못되면 포커 외 다른 게임 용어가 튀는 경우가 많다.
- 내부적으로 `build_decision_context()`를 사용한다.
- 현재 출력 상한은 `64` 토큰이다.
- `build_draw_prompt()`에 족보별 교체 규칙(원페어: 페어 2장 유지, 나머지에서 버림 등)이 없으면 모델이 페어 카드를 버리는 잘못된 선택을 한다.

## 4. `prompts.py`

이 파일은 실제 판단 프롬프트 문장을 만든다.

### `build_public_state_text(match, legal_actions)`

기능:

- 현재 공개 상태를 읽기 쉬운 텍스트로 묶는다.

입력:

- 매치
- 합법 행동 목록

출력:

- 공개 상태 문자열

### `build_action_prompt(legal_actions)`

기능:

- 행동 선택용 최종 지시문 생성

핵심 요구:

- 공개 상태와 최근 흐름만 보고 판단
- JSON 하나만 출력

### `build_draw_prompt(max_discards)`

기능:

- 카드 교체용 최종 지시문 생성

핵심 요구:

- 인덱스 범위
- 최대 장수
- JSON 출력 형식

현재 빌드에서는 대사 생성 프롬프트를 쓰지 않는다.
게임 화면 문장은 `poker_dialogue.rpy`의 시스템 나레이션이 담당한다.

### `build_policy_feedback_prompt()`

기능:

- 회고를 위한 정책 슬롯을 요청

출력 형식:

- `result`
- `ending`
- `pressure`
- `bot_hand_bucket`
- `adjustment`
- `strategy_focus`

중요:

- Qwen은 자유 문장 3개를 직접 쓰지 않는다.
- 먼저 위 슬롯만 고르고, `runtime.py`가 그것을 `short_term`, `long_term`, `strategy_focus` 문장으로 변환한다.
- 이 구조 덕분에 4B 모델이 사실을 틀리게 섞을 여지가 줄어든다.
- `strategy_focus`

## 5. `tools.py`

이 파일은 Qwen-Agent가 호출하는 읽기 전용 도구를 정의한다.

### `set_tool_context(context)` / `clear_tool_context()`

기능:

- 현재 요청에 필요한 매치와 기억 문맥을 도구가 읽게 한다.

위험:

- 요청 끝나고 `clear_tool_context()`를 안 하면 이전 요청 문맥이 샌다.

### `GetPublicStateTool`

기능:

- 현재 공개 상태 텍스트 반환

입력:

- 없음

출력:

- 공개 상태 문자열

### `GetMemoryTool`

기능:

- 단기/장기 기억 일부 반환

입력:

- scope
- limit

출력:

- 기억 문자열

중요:

- `limit`를 명시하지 않으면 현재는 자르지 않고 전부 돌려준다.

### `GetRecentLogTool`

기능:

- 최근 공개 로그 반환

중요:

- `limit`를 명시하지 않으면 현재는 자르지 않고 전부 돌려준다.

### `GetRoundSummaryTool`

기능:

- 라운드 종료 요약 반환

도구 계층의 철칙:

- 읽기 전용
- 상태를 바꾸지 않음
- 공개 정보와 내부 정보를 섞지 않음

## 6. `runtime.py`

이 파일은 실제 모델이 도는 곳이다.

핵심 구성:

- 출력 정리 helper
- 시스템 메시지 builder
- `LocalTransformersFnCallModel`
- `QwenRuntime`
- IPC 루프

### 출력 정리 helper

중요 함수:

- `preview_text()`
- `looks_like_meta_response()`
- `normalize_reason_text()`
- `extract_action_payload()`
- `extract_draw_payload()`

역할:

- 모델이 낸 텍스트를 실제 게임에 쓸 수 있는 구조로 정리

위험:

- 여기서 과한 후처리를 넣으면 출력 품질을 숨기게 된다.
- 여기서 검증이 약하면 메타 텍스트가 그대로 게임에 들어간다.

### 시스템 메시지 builder

중요 함수:

- `build_decision_system_message()`
- `build_policy_system_message()`

원칙:

- decision: 합법성과 판단 형식
- policy: 회고 목적

중복 주입 금지:

- 시스템 메시지와 프롬프트에서 같은 역할 지시를 반복하면 모델이 오히려 그 문장을 따라 말한다.

### `LocalTransformersFnCallModel`

역할:

- Qwen-Agent가 로컬 transformers 모델을 함수호출형으로 쓰게 맞춘다.

입력:

- tokenizer
- model
- generation config

출력:

- Qwen-Agent가 읽는 메시지 시퀀스

주의 — `_postprocess_messages` 오버라이드:

- qwen-agent 0.0.34는 텍스트에서 function_call을 파싱해 Message를 만들 때 `extra=None`을 만들 수 있다.
- 런타임은 메시지 순회와 선택 결과 파싱 단계에서 `None`과 `extra=None`을 먼저 방어해야 한다.
- 현재 대사 경로는 직접 생성이다. 이벤트별 상황, 최근 실제 행동, 직전 대사 흐름을 프롬프트에 넣고 `run_chat()`으로 대사를 만든다.

### `QwenRuntime`

역할:

- task 종류별 실행
- tool context 세팅
- agent 호출
- 결과 구조화

입력:

- task payload

출력:

- `{status: ok|error, ...}`

주의:

- `load_model()`에서 `decision_agent`, `policy_agent`를 초기화해야 한다.

### `serve_ipc(runtime)`

역할:

- stdin으로 JSON 요청을 받고 stdout으로 JSON 응답을 낸다.

의미:

- 현재 배포 구조는 HTTP 포트가 아니라 로컬 IPC다.

다음 장: [04. 기억, 회고, 세이브](04_memory_and_save.md)
