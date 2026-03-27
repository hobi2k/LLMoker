# Qwen-Agent 기록 문서

## 1. 현재 상태

현재 실행 경로는 `Qwen-Agent + transformers + stdin/stdout IPC`다.

이 구조에서 `Qwen-Agent`는 보조 레이어가 아니라 실제 판단 오케스트레이션의 기반이다.

정리하면:

- `Qwen-Agent`가 행동과 카드 교체의 오케스트레이션 중심이다.
- `transformers`가 실제 로컬 모델 추론을 맡는다.
- Ren'Py 3.9와 Python 3.11 `.venv`를 잇기 위해 IPC 런타임을 쓴다.

현재 활성 파일은 아래다.

- `llmoker/backend/llm/agent.py`
- `llmoker/backend/llm/client.py`
- `llmoker/backend/llm/runtime.py`
- `llmoker/backend/llm/tools.py`
- `llmoker/backend/llm/tasks.py`
- `llmoker/backend/llm/prompts.py`

## 2. 현재 역할 분리

- `agent.py`
  - 포커 엔진이 쓰는 상위 어댑터
- `client.py`
  - IPC 자식 프로세스 기동/종료/요청 전송
- `runtime.py`
  - 모델 로드, Qwen-Agent `FnCallAgent`, 결과 파싱
  - 행동/교체/회고는 tool calling 경로를 쓴다.
  - 회고는 `short_term`, `long_term`, `strategy_focus`를 LLM이 직접 작성한다.
  - 런타임은 역할 용어와 필수 필드만 정규화하고, `policy_loop.py`가 공개 사실 기준으로 후검증한다.
- `tools.py`
  - `get_public_state`, `get_memory`, `get_recent_log`, `get_round_summary`
- `tasks.py`
  - 행동/교체 태스크 payload 조립
  - 행동/교체 태스크에 최근 전략 피드백과 장기 기억을 함께 넣는다.
  - 회고 태스크에는 이번 라운드의 확정 사실과 행동 사실만 넣는다.
- `prompts.py`
  - 작업 prompt 조립

## 3. 백업 위치

이전 `vLLM` 서버-클라이언트 구조는 공부용으로 남겨 둔다.

- 백업 위치: `llmoker/backend/llm/vllm_backup/`
- 백업 파일:
  - `client.py`
  - `runtime.py`

이 백업은 현재 실행 경로가 아니다.

## 4. 읽는 순서

현재 구조를 따라 읽으려면 이 순서가 가장 빠르다.

1. [LLM 서빙 구조](serving.md)
2. `llmoker/backend/llm/agent.py`
3. `llmoker/backend/llm/tasks.py`
4. `llmoker/backend/llm/prompts.py`
5. `llmoker/backend/llm/tools.py`
6. `llmoker/backend/llm/client.py`
7. `llmoker/backend/llm/runtime.py`

## 5. 현재 화면 출력 메모

현재 빌드에서는 LLM 대사를 사용하지 않는다.

- `poker_dialogue.rpy`는 행동 요약과 단계 나레이션만 출력한다.
- 게임 화면의 문장은 `플레이어는 체크했다`, `사야는 10칩 베팅했다`처럼 시스템 설명으로 통일한다.
- 정책 회고는 `policy_loop.py`가 공개 로그와 라운드 결과를 LLM 회고 입력으로 넘겨 생성한다.
- 정책 회고는 라운드 종료 뒤 한 번만 생성한다.
- `policy_loop.py`는 회고 결과가 승패, 족보, 폴드 종료 여부와 충돌하면 저장하지 않는다.
- 베팅이 없는 상태에서는 `fold`를 합법 행동으로 주지 않는다.
- 플레이어와 사야는 같은 기준으로 행동 공간이 열린다.
  - `to_call == 0`이면 `check`, `bet`
  - `to_call > 0`이면 `fold`, `call`, `raise`
- 즉 Qwen 런타임은 행동, 카드 교체, 회고를 처리한다.
- 행동과 카드 교체는 저장된 회고를 읽어 다음 판단에 반영한다.
