# LLM NPC 설정 문서

## 1. 목적

이 문서는 현재 기본 모델 `llmoker/models/llm/qwen3-4b-thinking`를 기준으로, LLM NPC가 어떤 파일 구조와 런타임 경계를 통해 동작하는지 정리한다.

## 2. 현재 구조

현재 LLM 레이어는 아래처럼 분리한다.

1. `backend/poker_engine.py`
   포커 규칙과 공개/비공개 정보 경계를 관리한다.
2. `backend/llm/agent.py`
   포커 상태를 받아 행동, 카드 교체, 대사 생성, 정책 피드백 생성을 요청한다.
3. `backend/llm/prompts.py`
   공개 상태 문자열과 Qwen-Agent tool-calling 프롬프트를 조합한다.
4. `backend/llm/worker_client.py`
   `backend/llm/runtime_worker.py` 서브프로세스를 관리한다.
5. `backend/llm/runtime_worker.py`
   Qwen-Agent 요청을 별도 프로세스로 보내고 응답을 정리한다.
6. `backend/llm/tools.py`
   Qwen-Agent가 호출하는 포커 전용 도구를 정의한다.
7. `backend/poker_hands.py`
   카드 포맷팅, 덱 생성, 족보 비교를 담당한다.
8. `backend/script_bot.py`
   규칙 기반 스크립트봇 행동과 드로우 판단을 담당한다.

새 코드는 `backend/llm/` 아래를 직접 기준으로 본다.

`Qwen-Agent` 레이어를 왜 이렇게 나눴는지, 각 파일이 어떤 책임을 가지는지는 [qwen_agent.md](docs/qwen_agent.md)에 따로 정리한다.

## 3. 현재 모델과 백엔드

- 기본 모델 경로: `llmoker/models/llm/qwen3-4b-thinking`
- 공식 다운로드 경로: `https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507`
- 기본 디바이스 힌트: `auto`
- 기본 상대 AI: `LLM NPC`
- 현재 LLM NPC 경로:
  - `Qwen-Agent Assistant`
  - `local transformers runtime`

중요한 전제:

- `qwen_agent`는 로컬 `transformers` 백엔드와 함께 사용한다.
- 워커는 모델을 직접 로드하고, 별도 모델 서버를 띄우지 않는다.
- 기본 디바이스는 `auto`다. CUDA가 보이면 GPU를 쓰고, 아니면 CPU로 내린다.
- 모델 로딩 실패 시 스크립트봇이나 다른 백엔드로 자동 폴백하지 않는다.
- 실패 원인은 게임 상태 문구와 터미널 디버그 로그에 그대로 남긴다.

## 4. Qwen3 대응 원칙

Qwen3-4B-Thinking-2507 모델 카드와 Qwen-Agent 공식 문서 기준으로 현재 워커는 아래 원칙을 따른다.

- 기본 경로는 `Qwen-Agent + local transformers` 조합이다.
- Qwen-Agent 쪽 에이전트 타입은 `Assistant`를 사용한다.
- 로컬 모델 폴더 안 파일은 수정하지 않는다.
- 현재는 로컬 `transformers` 로더에도 원본 모델 폴더를 그대로 전달한다.
- Qwen 기본 chat template가 `<think>` 구간을 만들 수 있으므로, 행동 JSON 파싱과 대사 추출은 `</think>` 뒤 최종 응답만 사용한다.
- `Qwen-Agent`의 `generate_cfg`는 로컬 `transformers`에서 바로 먹는 샘플링 인자만 전달한다.

Qwen-Agent를 사용할 때는 아래 입력을 함께 쓴다.

- `llm_model_name`
- `local_llm_path`
- `llm_device`

현재 기본 모델 이름은 `Qwen3-4B-Thinking-2507`로 맞춘다.

현재 연결된 도구는 아래 네 가지다.

- `get_public_state`
- `get_memory`
- `get_recent_log`
- `get_round_summary`

## 5. 정보 공개 규칙

LLM NPC는 아래 정보만 볼 수 있다.

- 자기 손패
- 현재 팟
- 양측 스택
- 현재 콜 금액
- 현재 합법 행동
- 공개 진행 로그
  - 체크
  - 베팅
  - 콜
  - 레이즈
  - 폴드
  - 카드 교체 여부와 교체 장수

LLM NPC가 보면 안 되는 정보:

- 플레이어 현재 손패
- 플레이어 드로우 후 실제 카드 구성

이를 위해 엔진은 아래 두 로그를 분리한다.

- `action_log`
  - 디버그와 전체 진행 추적용 로그
- `public_log`
  - LLM 프롬프트에 들어가도 되는 공개 정보만 담는 로그

프롬프트는 항상 `public_log` 기준으로 조합한다.

## 6. 실패 정책

현재 `LLM NPC` 모드에서는 아래를 숨기지 않는다.

- 행동 선택 실패
- 카드 교체 판단 실패
- 대사 생성 실패
- 정책 피드백 생성 실패

즉, 스크립트봇이나 안전 행동으로 조용히 대체하지 않는다. 문제가 있으면 바로 고치기 쉽게 오류를 그대로 드러내는 쪽을 택한다.

## 7. 대사 생성 구조

대사 생성 흐름은 아래와 같다.

1. `game/poker_dialogue.rpy`가 이벤트 발생 지점을 잡는다.
2. `backend/llm/agent.py`가 공개 상태와 최근 공개 로그를 모은다.
3. `backend/llm/prompts.py`가 대사 프롬프트를 조합한다.
4. `backend/llm/runtime_worker.py`가 Qwen-Agent와 도구를 연결한다.
5. Qwen-Agent는 필요할 때 `get_public_state`, `get_recent_log`, `get_memory`를 호출한다.
6. 워커는 `</think>` 뒤 최종 대사만 추출해 반환한다.

## 7.1 정책 피드백 생성 구조

정책 피드백 흐름은 아래와 같다.

1. `backend/poker_engine.py`가 라운드 종료 시 `round_summary`와 `public_log`를 만든다.
2. `backend/policy_loop.py`가 이를 받아 LLM 정책 리뷰를 요청한다.
3. `backend/llm/prompts.py`가 정책 피드백 프롬프트를 조합한다.
4. `backend/llm/agent.py`가 워커에 `policy` 모드 요청을 보낸다.
5. `backend/llm/runtime_worker.py`가 `get_round_summary`, `get_recent_log`, `get_memory` 도구를 연결한다.
6. 워커가 `short_term`, `long_term`, `strategy_focus` JSON을 반환한다.
7. `backend/memory_manager.py`가 단기/장기 기억으로 저장한다.

즉, `policy_loop`는 더 이상 단순 규칙 문자열 생성기가 아니라, LLM 정책 회고를 메모리 형식으로 적재하는 경계 레이어다.

## 8. 현재 의존성

LLM NPC를 실제 추론까지 쓰려면 `.venv` 환경에 아래 패키지가 필요하다.

- `torch`
- `qwen-agent`
- `transformers`

모델이 비어 있거나 일부 파일만 남아 있으면 `./5Drawminigame.sh`가 먼저 자동 다운로드를 시도한다.
자동 다운로드가 실패하면 아래 경로를 안내하고, 사용자가 직접 모델을 내려받아 배치하도록 한다.

- 다운로드: `https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507`
- 배치 위치: `llmoker/models/llm/qwen3-4b-thinking`
- 자동 다운로드를 끄고 직접 관리하려면 `LLMOKER_SKIP_MODEL_DOWNLOAD=1 ./5Drawminigame.sh`로 실행한다.

현재 권장 설치 예시는 아래와 같다.

```bash
llmoker/.venv/bin/python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
llmoker/.venv/bin/python -m pip install protobuf qwen-agent transformers
```

## 9. 주요 파일

- [agent.py](llmoker/backend/llm/agent.py)
- [prompts.py](llmoker/backend/llm/prompts.py)
- [worker_client.py](llmoker/backend/llm/worker_client.py)
- [tools.py](llmoker/backend/llm/tools.py)
- [runtime_worker.py](llmoker/backend/llm/runtime_worker.py)
- [poker_engine.py](llmoker/backend/poker_engine.py)

## 10. 관련 문서

- [블루프린트](docs/blueprint.md)
- [대사 시스템](docs/dialogue_system.md)
- [ICRL 정책 업데이트](docs/icrl_policy_update.md)
- [Ren'Py 런타임 구조](docs/renpy_engine.md)
