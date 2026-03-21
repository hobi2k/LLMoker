# Qwen-Agent 구조 문서

## 1. 목적

이 문서는 `LLMoker`에서 `Qwen-Agent`를 어떻게 붙였는지, 왜 현재 폴더 구조가 그렇게 생겼는지, 각 파일이 실제로 무슨 책임을 가지는지 따로 설명한다.

이 문서는 특히 아래 질문에 답하기 위해 둔다.

- 왜 `Qwen-Agent`를 바로 Ren'Py 안에서 호출하지 않는가
- 왜 `backend/llm/`가 따로 있는가
- 왜 `runtime_worker.py`와 `worker_client.py`가 둘 다 필요한가
- 왜 `scripts/`는 개발용만 남기려 하는가

## 2. 현재 구조

현재 `Qwen-Agent` 레이어는 아래 파일들로 구성된다.

1. `llmoker/backend/llm/agent.py`
   - 포커 엔진이 직접 호출하는 상위 어댑터다.
   - 행동 선택, 카드 교체, 대사 생성, 정책 회고 요청을 한 곳에서 묶는다.
2. `llmoker/backend/llm/prompts.py`
   - `Qwen-Agent`에 넘길 프롬프트를 조합한다.
   - 공개 상태, 최근 로그, 기억을 어떤 방식으로 문장화할지 여기서 정한다.
3. `llmoker/backend/llm/tools.py`
   - `Qwen-Agent` tool calling에서 실제로 노출할 도구 집합을 정의한다.
   - 현재 도구는 `get_public_state`, `get_memory`, `get_recent_log`, `get_round_summary` 네 가지다.
4. `llmoker/backend/llm/worker_client.py`
   - Ren'Py 본체 입장에서 `Qwen-Agent` 로컬 워커를 관리하는 프로세스 클라이언트다.
   - 워커 재사용, 실패 캐시, IPC를 맡는다.
5. `llmoker/backend/llm/runtime_worker.py`
   - 별도 프로세스에서 실제 `Qwen-Agent Assistant`를 띄우는 실행 진입점이다.
   - tool calling 결과를 받아 JSON 라인 프로토콜로 본체에 돌려준다.
6. `llmoker/backend/poker_hands.py`
   - 카드 포맷팅, 덱 생성, 족보 평가 같은 포커 공용 규칙을 모아 둔다.
7. `llmoker/backend/script_bot.py`
   - LLM 없이도 완전한 한 판을 진행할 수 있는 규칙 기반 상대를 분리해 둔다.

## 3. 왜 이런 폴더 구조인가

핵심 이유는 `Ren'Py`, `Qwen-Agent`, `transformers`의 런타임 경계를 섞지 않기 위해서다.

- Ren'Py 본체는 게임 루프와 UI를 담당한다.
- `Qwen-Agent`는 tool calling과 대화형 추론 레이어를 담당한다.
- 로컬 모델 추론은 `transformers` 기반 워커에서 돈다.
- 기본 디바이스는 `auto`다. CUDA가 보일 때만 GPU를 쓰고, 아니면 CPU로 내린다.

이 셋을 한 프로세스에 몰아 넣으면 아래 문제가 생기기 쉽다.

- Ren'Py 런타임과 LLM 의존성이 직접 충돌할 수 있다.
- 모델 로딩 실패, 워커 재시도, IPC 로직이 UI 코드 안으로 새어 나온다.
- 포커 엔진이 `qwen_agent` 세부 API를 직접 알게 된다.

그래서 현재 구조는 아래 분리를 목표로 잡았다.

- `backend/poker_engine.py`
  - 규칙과 상태 진실의 원천
- `backend/llm/*.py`
  - LLM 계층
- `game/*.rpy`
  - Ren'Py UI와 연출

즉 이 구조는 “예쁘게 보이려고 쪼갠 것”이 아니라, 런타임 경계를 강제로 분리하려고 생긴 구조다.

## 4. 왜 `scripts/`가 아니고 `backend/llm/`인가

처음에는 런타임 워커가 `scripts/llm_runtime_worker.py`에 있었는데, 그건 구조상 맞지 않았다.

이유:

- `scripts/`는 개발자가 수동으로 돌리는 보조 스크립트 폴더로 읽힌다.
- 그런데 `llm_runtime_worker.py`는 실제 게임에서 쓰는 런타임 코드였다.
- 이 상태에선 “개발용 스크립트”와 “게임이 실제로 의존하는 코드”가 섞여서 읽는 사람이 헷갈린다.

그래서 지금은 이렇게 정리했다.

- `llmoker/backend/llm/runtime_worker.py`
  - 실제 런타임 워커
- `llmoker/scripts/run_match.py`
  - 개발용 CLI 테스트

즉 현재 기준에서 `scripts/`는 개발용만 두는 게 맞다.

## 5. 현재 구조의 장점

- 포커 엔진이 `Qwen-Agent` 세부 구현에 직접 묶이지 않는다.
- `Qwen-Agent` 프롬프트, 도구, 워커를 UI 코드와 분리해 읽을 수 있다.
- 실패 원인을 `worker_client.py`에서 한 군데로 모아 관리할 수 있다.
- `runtime_worker.py`를 따로 띄워 Ren'Py 본체와 모델 추론 프로세스를 분리할 수 있다.
- 모델 원본 파일은 수정하지 않는다.

## 6. 현재 구조의 문제점

현재 구조가 완벽하다는 뜻은 아니다. 실제 문제도 있다.

- `agent.py`와 `runtime_worker.py` 사이 요청/응답 형식이 문자열 중심이라 아직 매끈하지 않다.
- `worker_client.py`가 워커 재기동, 실패 캐시, IPC를 다 떠안아 비대하다.
- `results.py`는 지금 규모에선 이득보다 과분리로 느껴질 수 있다.
- `Qwen-Agent + transformers + Ren'Py`를 엮다 보니 구조가 단순한 프로젝트보다 무겁다.

즉 현재 구조는 “최종형”이 아니라, 런타임 충돌을 피하려고 분리한 1차 정리 구조다.

## 7. 실제 호출 흐름

현재 한 번의 LLM 요청은 아래 순서로 돈다.

1. `game/*.rpy`가 포커 엔진 메서드를 호출한다.
2. `backend/poker_engine.py`가 `LocalLLMAgent`를 호출한다.
3. `backend/llm/agent.py`가 프롬프트와 문맥을 만든다.
4. `backend/llm/worker_client.py`가 워커 준비 상태를 확인한다.
5. `backend/llm/runtime_worker.py`가 `Qwen-Agent Assistant`를 실행한다.
6. `backend/llm/tools.py`의 도구가 호출된다.
7. 최종 응답이 다시 엔진으로 돌아와 합법성 검증을 거친다.

핵심은 마지막 단계다.

- LLM은 제안만 한다.
- 최종 행동 적용은 포커 엔진이 한다.

## 8. 읽는 순서

`Qwen-Agent` 레이어를 읽을 때는 아래 순서가 가장 낫다.

1. `llmoker/backend/poker_engine.py`
2. `llmoker/backend/llm/agent.py`
3. `llmoker/backend/llm/prompts.py`
4. `llmoker/backend/llm/tools.py`
5. `llmoker/backend/llm/worker_client.py`
6. `llmoker/backend/llm/runtime_worker.py`
7. `llmoker/backend/poker_hands.py`
8. `llmoker/backend/script_bot.py`

이 순서를 벗어나면 서버 관리와 프롬프트와 엔진이 한꺼번에 보여서 더 읽기 어려워진다.

## 9. 관련 파일

- [agent.py](llmoker/backend/llm/agent.py)
- [prompts.py](llmoker/backend/llm/prompts.py)
- [tools.py](llmoker/backend/llm/tools.py)
- [worker_client.py](llmoker/backend/llm/worker_client.py)
- [runtime_worker.py](llmoker/backend/llm/runtime_worker.py)
- [poker_hands.py](llmoker/backend/poker_hands.py)
- [script_bot.py](llmoker/backend/script_bot.py)
- [poker_engine.py](llmoker/backend/poker_engine.py)
