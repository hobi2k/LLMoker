# 03. LLM 백엔드와 Qwen-Agent

[목차로 돌아가기](README.md)

이 장은 **LLMoker의 현재 활성 LLM 구조**를 설명한다.  
핵심은 `Qwen-Agent가 지금의 기반`이라는 점이다.  
이 장은 “에이전트를 얹는” 구조가 아니라, 에이전트 중심으로 어떻게 판단이 조립되는지 보는 장이다.

정리하면, `transformers`는 실제 추론 엔진이고 `Qwen-Agent`는 행동, 카드 교체, 대사, 회고를 한 흐름으로 묶는 기본 오케스트레이션 계층이다.

## 1. 전체 구조

현재 활성 경로:

- `agent.py`
- `client.py`
- `runtime.py`
- `tasks.py`
- `prompts.py`
- `tools.py`

실제 흐름:

1. 엔진이 “행동/카드 교체/대사/회고가 필요하다”고 판단한다.
2. `LocalLLMAgent`가 현재 상황을 task로 만든다.
3. `QwenRuntimeClient`가 외부 Python 3.11 런타임에 요청한다.
4. `runtime.py`가 `Qwen-Agent + transformers`로 결과를 만든다.
5. 결과를 다시 엔진이 검증하고 적용한다.

중요한 점:

- 이 런타임은 첫 대사 요청 때 늦게 띄우지 않는다.
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

프로그램 시작 직후 스플래시 시퀀스 동안 런타임을 미리 올려 두고, 첫 대사나 첫 행동에서 느껴지는 지연을 줄이기 위해 사용된다.

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

### `generate_dialogue(match, event_name, result_summary=None)`

기능:

- 현재 이벤트에 맞는 심리전 대사를 생성한다.

입력:

- 매치
- 이벤트 이름
- 종료 요약 문자열

출력:

- `{status, text, reason}`

대사 품질이 이상할 때는 이 함수 하나만 보면 안 된다.  
반드시 `build_dialogue_task()`, `build_dialogue_prompt()`, `runtime.py`의 dialogue 시스템 메시지를 같이 봐야 한다.

### `generate_policy_feedback(round_summary, public_log, bot_name)`

기능:

- 라운드 회고를 요청한다.

입력:

- 라운드 요약
- 공개 로그
- 봇 이름

출력:

- `{status, short_term, long_term, strategy_focus}`

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

- 행동과 카드 교체는 최근 기억을 직접 섞지 않는다.
- 공개 상태와 공개 로그만 넘겨, 회고 문장이나 장기 메모가 현재 판단을 오염시키지 않게 한다.
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

### `build_dialogue_task(...)`

기능:

- 대사 생성용 task 생성

중요:

- 여기서 최근 공개 사건을 어떻게 요약하느냐가 대사 품질을 크게 좌우한다.
- 로그를 날것으로 넘기면 프롬프트 복제형 대사가 나오기 쉽다.
- `round_end`, `match_end`는 `round_summary`를 읽고 감정 힌트를 따로 만든다.
- 현재 출력 상한은 `80` 토큰이다.

### `build_policy_task(...)`

기능:

- 회고 생성용 task 생성

중요:

- 회고 품질이 나쁘면 기억이 오염된다.
- 현재 출력 상한은 `384` 토큰이다.

## 4. `prompts.py`

이 파일은 실제 문장을 만든다.  
대사 품질이 낮으면 가장 먼저 이 파일을 의심해야 한다.

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

### `build_dialogue_prompt(...)`

기능:

- 현재 사건에 맞는 대사 생성 지시문 생성

입력:

- 이벤트 이름
- 최근 공개 로그
- 결과 요약
- 플레이어/봇 이름

출력:

- 대사 프롬프트 문자열

현재 기준 핵심:

- 프롬프트는 `상대에게 지금 바로 한마디 던진다`는 직접 화법 중심이다.
- `방금 상황은 ...`, `지금 감정이나 목표는 ...` 정도만 짧게 준다.
- `블라인드`, `턴`, `라이브` 같은 설명투 표현을 금지한다.
- 대사 품질 문제를 후처리보다 입력 문맥 축소와 사건 재서술로 해결하려는 경로다.

가장 자주 흔들리는 지점:

- 프롬프트 문장을 모델이 그대로 비틀어 말함
- 장면 설명을 대사처럼 따라 함
- 없는 게임 용어를 지어냄

### `build_policy_feedback_prompt()`

기능:

- 회고와 전략 초점 생성을 요청

출력 형식:

- `short_term`
- `long_term`
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
- `extract_dialogue_text()`
- `normalize_dialogue_text()`
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

- `build_dialogue_system_message()`
- `build_decision_system_message()`
- `build_policy_system_message()`

원칙:

- dialogue: 캐릭터성과 대화 스타일
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

### `serve_ipc(runtime)`

역할:

- stdin으로 JSON 요청을 받고 stdout으로 JSON 응답을 낸다.

의미:

- 현재 배포 구조는 HTTP 포트가 아니라 로컬 IPC다.

다음 장: [04. 기억, 회고, 세이브](04_memory_and_save.md)
