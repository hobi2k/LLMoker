# 대사 시스템 설계

## 1. 목적

`LLMoker`는 포커 엔진만 있는 게임이 아니라, 캐릭터성과 심리전 연출이 같이 돌아가는 구조를 목표로 한다.

그래서 각 라운드의 시작과 종료, 그리고 베팅/드로우 같은 핵심 지점마다 캐릭터 대사가 들어가야 한다.

## 2. 현재 구현 위치

현재 스크립트 대사 레이어는 아래 파일에 들어 있다.

- [poker_dialogue.rpy](/home/hosung/pytorch-demo/LLMoker/llmoker/game/poker_dialogue.rpy)
- [poker_minigame.rpy](/home/hosung/pytorch-demo/LLMoker/llmoker/game/poker_minigame.rpy)
- [prompt_builder.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/prompt_builder.py)
- [llm_agent.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/llm_agent.py)

## 3. 현재 이벤트 훅

현재 대사는 아래 이벤트에서 호출된다.

1. `match_intro`
   - 매치 시작 전 첫 진입 대사
2. `round_start`
   - 새 라운드 시작 직후
3. `betting`
   - 체크, 베팅, 콜, 레이즈, 폴드 이후 반응
4. `draw`
   - 플레이어가 교체 선택을 끝낸 직후
5. `round_end`
   - 라운드 결과가 확정된 직후
6. `match_end`
   - 한쪽 스택 부족으로 더 이상 라운드를 열 수 없을 때

## 4. 현재 구조

현재는 스크립트 기반 대사다.

- `_dialogue_event_lines(event_name, messages=None)`
  - 이벤트별 대사 후보를 고른다.
- `play_dialogue_event(event_name, messages=None)`
  - 선택된 대사를 Ren'Py 대사창에 순서대로 출력한다.

이미지 규칙:

- 일반 대사 이벤트는 `images/minigames/bunny.png`
- 결과 대사 이벤트 `round_end`, `match_end`는 `images/minigames/bunny2.png`
- 포커 기본 배경은 `images/minigames/normal.webm`
- 라운드 종료 배경은 플레이어 승리 시 `images/minigames/lost.webm`, NPC 승리 시 `images/minigames/win.webm`

즉, 지금은 규칙 기반 이벤트 대사를 먼저 넣고, 나중에 같은 위치에 LLM 생성 대사를 연결할 수 있게 만든 상태다.

대사 심리전의 정보 경계도 행동 판단과 동일하다.

- 대사 생성도 공개된 베팅/체크/레이즈/폴드/교체 정보만 사용해야 한다.
- 플레이어 실제 손패는 대사 생성 프롬프트에 포함하면 안 된다.

### 4.1 현재 실제 연결 상태

여기서 가장 중요한 건 “구조만 있는지”, “실제로 호출되는지”를 분리해서 보는 것이다.

현재 상태는 아래와 같다.

- `play_dialogue_event(...)`
  - 실제 게임 중 호출된다.
- `_dialogue_event_lines(...)`
  - LLM 실패 시 사용할 스크립트 폴백 대사를 제공한다.
- `build_dialogue_prompt(...)`
  - 실제 대사 생성 프롬프트를 만든다.
- `LocalLLMAgent.generate_dialogue(...)`
  - 실제로 로컬 모델 워커를 호출한다.

즉, 현재 대사 시스템은:

- 이벤트 훅은 실제로 동작함
- LLM 대사 생성 경로가 실제로 연결됨
- 실패 시 스크립트 대사로 폴백함

## 5. LLM 연결 방향

현재는 아래 구조로 동작한다.

1. 이벤트 발생
2. 현재 포커 상태 수집
3. 캐릭터 기억과 최근 로그 수집
4. `backend/prompt_builder.py`로 프롬프트 구성
5. `backend/llm_agent.py`가 워커에 대사 생성 요청
6. 성공 시 생성 대사 출력
7. 실패 시 스크립트 대사로 폴백

즉, 대사 시스템은 아래 구조다.

`LLM 대사 우선 -> 실패 시 스크립트 대사 폴백`

현재 프롬프트 빌더 기준:

- `build_action_prompt(...)`
  - 행동 선택용 프롬프트
- `build_dialogue_prompt(...)`
  - 대사 생성용 프롬프트

### 5.1 대사 프롬프트 입력 요소

`build_dialogue_prompt(...)`는 아래 입력을 받도록 설계되어 있다.

- `event_name`
  - 어떤 대사 이벤트인지
- `public_state`
  - 현재 공개 포커 상태
- `recent_feedback`
  - 최근 전략 피드백
- `long_term_memory`
  - 장기 기억
- `recent_log`
  - 최근 공개 게임 로그
- `result_summary`
  - 라운드 결과 요약
- `player_name`
  - 실제로 말을 거는 상대 이름
- `bot_name`
  - 현재 대사를 생성하는 NPC 이름

즉, 단순한 한 줄 대사가 아니라:

`이벤트 종류 + 현재 포커 상태 + 최근 로그 + 기억 + 결과 요약 + 화자/청자 관계`

을 합쳐 심리전 대사를 만들도록 설계된 상태다.

### 5.2 현재 동작 규칙

- 대사 생성에도 플레이어 손패는 노출하지 않는다.
- 최근 공개 로그와 결과 요약만 사용한다.
- 플레이어에게 직접 말하는 2인칭 대사로 제한한다.
- 직전 공개 행동이나 결과에 직접 반응하도록 강하게 유도한다.
- 설명문, 해설문, 요약문 대신 실제 대화처럼 들리는 짧은 반응을 우선한다.
- 생성 대사는 최대 두 줄로 정리한다.
- 출력 실패 시 현재 스크립트 대사를 그대로 사용한다.
- 대사 생성 성공 시 내부 로그에 `[LLM NPC] ... 대사 생성` 형식으로 남긴다.
- 대사 생성 결과는 터미널에도 `[LLMoker][DEBUG] ...` 형식으로 출력해 검증한다.

## 6. 현재 설계 원칙

- 포커 규칙 엔진과 대사 레이어는 분리한다.
- 대사는 결과를 설명하거나 심리전을 강화해야지, 규칙 판정을 대신하면 안 된다.
- 베팅/드로우/라운드 종료처럼 감정 변화가 큰 지점에만 넣는다.
- UI 흐름을 끊지 않도록 각 이벤트의 대사 수는 짧게 유지한다.
- 대사 이벤트에 맞는 캐릭터 이미지를 같이 전환한다.

## 7. 다음 확장 포인트

- 캐릭터별 페르소나 파일 연동
- 승패와 관계도에 따른 분기 대사
- 이전 라운드 기억 반영
- 블러프 성공/실패에 대한 장기 피드백 반영
- 쇼다운 직전 긴장 연출
