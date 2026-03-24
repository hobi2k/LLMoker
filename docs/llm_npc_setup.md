# LLM NPC 설정 문서

## 1. 목적

이 문서는 현재 기본 런타임 모델 `llmoker/models/llm/qwen3-4b-instruct-2507`를 기준으로,
LLM NPC가 어떤 파일 구조와 런타임 경계를 통해 동작하는지 정리한다.

현재 기준 핵심 전제는 아래와 같다.

- 기본 상대 AI는 `LLM NPC`
- LLM 경로는 `transformers` 기반 외부 런타임
- 실제 모델 실행은 Python 3.11 런타임 프로세스에서 한다
- 모델 원본 파일은 수정하지 않는다
- 기억은 전역 DB에 계속 누적하지 않고, 현재 매치에 붙어 다니다가 저장했을 때만 스냅샷으로 같이 복원한다

## 2. 현재 구조

현재 LLM 레이어는 아래처럼 분리한다.

1. `backend/poker_engine.py`
   - 포커 규칙과 공개/비공개 정보 경계를 관리한다.
2. `backend/llm/agent.py`
   - 포커 엔진이 직접 호출하는 상위 어댑터다.
   - 요청 흐름을 `태스크 생성 -> 런타임 요청 -> 결과 검증`으로 고정한다.
3. `backend/llm/tasks.py`
   - 행동 선택, 카드 교체 판단, 심리전 대사 생성, 라운드 회고 및 전략 업데이트를 명시적인 태스크 객체로 만든다.
4. `backend/llm/prompts.py`
   - 공개 상태 문자열과 태스크 프롬프트를 조합한다.
5. `backend/llm/client.py`
   - Ren'Py 3.9 프로세스에서 Python 3.11 런타임 프로세스를 띄우고 요청/응답을 관리한다.
6. `backend/llm/runtime.py`
   - Python 3.11에서 transformers 모델을 직접 로드하고 실행한다.
7. `backend/poker_hands.py`
   - 카드 포맷팅, 덱 생성, 족보 비교를 담당한다.
8. `backend/script_bot.py`
   - 규칙 기반 스크립트봇 행동과 드로우 판단을 담당한다.

배포용 서빙 구조와 이전 `vLLM` 백업 경로는 [serving.md](docs/serving.md)에 따로 정리한다.

중요한 전제 하나는 `Qwen-Agent`가 단순 부가기능이 아니라 이 구조의 기본 오케스트레이션 계층이라는 점이다.
행동 선택, 카드 교체, 대사 생성, 라운드 회고는 모두 `Qwen-Agent`를 통해 태스크와 도구 호출을 엮고, `transformers`는 그 아래 실제 추론을 담당한다.

## 3. 현재 모델과 실행 방식

- 기본 모델 경로: `llmoker/models/llm/qwen3-4b-instruct-2507`
- bootstrap 자동 다운로드 경로: `https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507`
- 기본 디바이스 힌트: `auto`
- 기본 상대 AI: `LLM NPC`
- 런타임은 `.venv` 기준 Python 3.11 프로세스에서 transformers로 모델을 직접 로드한다.
- 디바이스가 `auto`면 CUDA가 보일 때는 GPU, 아니면 CPU로 내려간다.

중요한 전제:

- Ren'Py 게임 프로세스는 런타임 클라이언트만 유지하고, 실제 모델 로드는 Python 3.11 런타임에서 진행한다.
- 기본 디바이스는 `auto`다. CUDA가 보이면 GPU를 쓰고, 아니면 CPU로 내린다.
- 프로그램 시작 직후 `label splashscreen`에서 Qwen 런타임 백그라운드 예열을 먼저 시작해서, 미니게임 진입 뒤 첫 대사 요청에서 모델 기동 비용이 한꺼번에 튀지 않게 한다.
- `5Drawminigame.sh`는 게임 종료, `Ctrl+C`, 프로세스 중단 시 Qwen 런타임 정리 명령을 같이 호출한다.
- 게임 시작 전 런타임 예열 실패 상세 내용은 `llmoker/data/logs/qwen_runtime_start.log`에 남긴다.
- 런타임 시작 실패 메시지는 traceback 전체 대신 마지막 핵심 원인 한 줄만 노출한다.
- 런타임 작업 실패 사유는 `error`나 `reason` 어느 키로 오더라도 그대로 로그와 상태 문구에 남긴다.
- 모델 로딩 실패 시 스크립트봇이나 다른 백엔드로 자동 폴백하지 않는다.
- 실패 원인은 게임 상태 문구와 터미널 디버그 로그에 그대로 남긴다.

## 4. Qwen3 대응 원칙

현재 런타임은 `Qwen3-4B-Instruct-2507`를 기본 모델로 사용하고, transformers 런타임이 모델을 직접 로드한다.
대사 생성만 시스템 메시지에 캐릭터 정체성과 말투를 두고, 행동/교체/회고 프롬프트는 판단 규칙과 출력 형식만 남겨 중복 지시를 줄인다.

- 기본 경로는 `transformers` 런타임이다.
- 로컬 모델 폴더 안 파일은 수정하지 않는다.
- Instruct 모델의 최종 응답 문자열을 그대로 읽고, 행동 JSON 파싱과 대사 추출은 그 문자열만 기준으로 한다.
- 대사 생성은 `runtime.py`의 `dialogue_agent`를 통해 Qwen-Agent 경로로 실행한다.
- 대사 프롬프트에는 최근 공개 로그를 그대로 넣지 않고, `상대가 체크했다`, `새 라운드 카드가 막 들어왔다`처럼 대사용 사건 문장 한 줄로 다시 써서 넣는다.
- 대사 프롬프트는 설명 라벨보다 `상대에게 지금 바로 던지는 말`, `방금 상황`, `감정/목표`를 짧게 적는 쪽으로 유지한다.
- `round_end`, `match_end`는 `round_summary`를 읽고 이겼으면 기쁨/우쭐함, 졌으면 분함/짜증 쪽 감정 힌트를 우선 준다.
- 행동과 카드 교체는 최근 기억을 직접 섞지 않고, `build_decision_context()`가 만든 공개 상태와 공개 로그만으로 판단하게 유지한다.
- Qwen-Agent 도구 기본 동작도 최근 로그와 기억을 임의 개수로 자르지 않고, `limit`를 명시했을 때만 제한한다.
- 메타 추론문처럼 보이는 응답만 남으면 실패로 처리한다.
- JSON이나 대사 정리에 실패하면, 오류 문구에 모델 최종 응답 일부를 함께 남긴다.
- 행동 이유 앞에 붙는 `check`, `fold`, `action:` 같은 형식용 접두는 로그에 남기지 않게 정리한다.
- 카드 교체 이유 앞에 붙는 `[0, 2]` 같은 인덱스 표기도 로그에서 걷어낸다.
- 행동과 교체 프롬프트는 JSON 형식만 남기고, 이유 문장에서 형식 토큰을 반복하지 않게 짧게 고정한다.
- 입력 문맥은 공백만 정리하고, 공개 로그와 기억 문장은 잘라서 버리지 않는다.
- IPC 런타임 요청은 기본 입력 상한 `896`, 작업별 출력 상한은 행동/드로우 `64`, 대사 `80`, 정책 회고 `384` 토큰으로 유지한다.
- 행동과 카드 교체는 한 번의 tool-calling 응답에서 바로 JSON이나 허용 행동을 읽는다.
- 행동 응답은 JSON뿐 아니라 `action: raise` 같은 짧은 태그형 출력도 읽을 수 있게 후처리한다.
- 함수 호출 프롬프트 타입은 Qwen 계열에 맞게 `qwen`으로 고정한다.
- 프롬프트 본문에는 역할, 장면, 최종 출력 형식만 짧게 둔다.
- 도구 사용 절차를 자연어로 길게 설명하지 않는다.
- `runtime.py`는 `agent.run(..., lang="en")` 같은 별도 언어 힌트를 더 이상 강제로 넣지 않는다.

게임 레벨 태스크는 아래 네 가지다.

- `행동 선택`
- `카드 교체 판단`
- `심리전 대사 생성`
- `라운드 회고 및 전략 업데이트`

## 5. 정보 공개 규칙과 기억 저장

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

기억은 현재 매치와 함께 다룬다.

- 새 게임을 시작하면 이전 세션 기억은 비운다.
- 세이브 슬롯에는 현재 매치 스냅샷과 함께 NPC 기억도 같이 저장한다.
- 불러오기를 하면 저장 당시 기억 상태를 함께 복원한다.
- 즉 저장하지 않고 게임을 껐다 켜면 이전 기억은 이어지지 않는다.

## 6. 실패 정책

현재 `LLM NPC` 모드에서는 아래를 숨기지 않는다.

- 행동 선택 실패
- 카드 교체 판단 실패
- 대사 생성 실패
- 정책 피드백 생성 실패

즉 스크립트봇이나 안전 행동으로 조용히 대체하지 않는다. 문제가 있으면 바로 고치기 쉽게 오류를 그대로 드러내는 쪽을 택한다.

## 7. 대사 생성 구조

대사 생성 흐름은 아래와 같다.

1. `game/script.rpy`의 `label splashscreen`이 로고, 안내 문구, 인트로, 오프닝 시퀀스를 재생하는 동안 `begin_llm_npc_prewarm()`으로 백그라운드 예열을 시작한다.
2. `label splashscreen` 끝에서 예열이 완전히 끝나도록 기다린 뒤 게임 시작으로 넘어간다.
3. `label start`는 이미 올라온 런타임 결과를 이어받는다.
4. `game/poker_dialogue.rpy`가 이벤트 발생 지점을 잡는다.
5. `backend/llm/agent.py`가 대사 태스크를 만든다.
6. `backend/llm/tasks.py`가 공개 상태와 최근 공개 로그를 대사 전용 사건 문맥으로 묶는다.
7. `backend/llm/prompts.py`가 대사 프롬프트를 조합한다.
8. `backend/llm/client.py`가 대사 태스크를 Python 3.11 런타임으로 전달한다.
9. `backend/llm/runtime.py`가 `dialogue_agent`로 대사를 생성한다.
10. 대사용 시스템 메시지는 사야의 말투와 직접 화법만 고정하고, 사건 요약과 감정 힌트는 프롬프트에서 따로 준다.

## 8. 정책 피드백 생성 구조

정책 피드백 흐름은 아래와 같다.

1. `backend/poker_engine.py`가 라운드 종료 시 `round_summary`와 `public_log`를 만든다.
2. `backend/policy_loop.py`가 이를 받아 LLM 정책 리뷰를 요청한다.
3. `backend/llm/agent.py`가 정책 태스크를 만든다.
4. `backend/llm/tasks.py`가 공개 로그, 회고 문맥, 기억을 태스크 객체로 묶는다.
5. `backend/llm/prompts.py`가 정책 피드백 프롬프트를 조합한다.
6. `backend/llm/runtime.py`가 transformers 모델로 회고 JSON을 생성한다.
7. `backend/memory_manager.py`가 단기/장기 기억으로 저장한다.

## 9. 현재 의존성

LLM NPC를 실제 추론까지 쓰려면 `.venv` 환경에 아래 패키지가 필요하다.

- `torch`
- `torchvision`
- `torchaudio`
- `numpy`
- `pydantic`
- `pydantic-core`
- `python-dateutil`
- `soundfile`
- `transformers`

모델이 비어 있거나 일부 파일만 남아 있으면 `./5Drawminigame.sh`가 먼저 자동 다운로드를 시도한다.
자동 다운로드가 실패하면 아래 경로를 안내하고, 사용자가 직접 모델을 내려받아 배치하도록 한다.

- 기본 배치 위치: `llmoker/models/llm/qwen3-4b-instruct-2507`
- bootstrap 다운로드: `https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507`
- 자동 다운로드를 끄고 직접 관리하려면 `LLMOKER_SKIP_MODEL_DOWNLOAD=1 ./5Drawminigame.sh`로 실행한다.
- 게임을 켜지 않고 런타임 태스크를 확인하려면 `llmoker/scripts/check_qwen_agent.py`를 실행한다.
- 모델 자체 raw 응답만 확인하려면 `llmoker/scripts/check_raw_inference.py`를 실행한다.

현재 권장 설치 예시는 아래와 같다.

```bash
llmoker/.venv/bin/python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
llmoker/.venv/bin/python -m pip install protobuf numpy pydantic pydantic-core python-dateutil soundfile transformers
```

## 10. TTS 확장

이 구조는 나중에 음성 TTS를 붙이는 쪽으로 확장하기 쉽다.

- `runtime.py`는 현재 텍스트 결과만 만든다.
- 추후에는 같은 응답 사전에 `voice_text`, `emotion`, `tts_payload`를 추가할 수 있다.
- Ren'Py는 그 결과만 받아 음성 재생 계층으로 넘기면 된다.

즉 TTS를 붙일 때 포커 엔진을 다시 갈아엎는 게 아니라, 런타임 응답 스키마를 확장하는 쪽이 맞다.

## 11. 주요 파일

- [agent.py](llmoker/backend/llm/agent.py)
- [client.py](llmoker/backend/llm/client.py)
- [runtime.py](llmoker/backend/llm/runtime.py)
- [tasks.py](llmoker/backend/llm/tasks.py)
- [prompts.py](llmoker/backend/llm/prompts.py)
- [tools.py](llmoker/backend/llm/tools.py)
- [poker_engine.py](llmoker/backend/poker_engine.py)

## 12. 관련 문서

- [블루프린트](docs/blueprint.md)
- [대사 시스템](docs/dialogue_system.md)
- [ICRL 정책 업데이트](docs/icrl_policy_update.md)
- [Ren'Py 런타임 구조](docs/renpy_engine.md)
