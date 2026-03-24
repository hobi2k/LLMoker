# Qwen-Agent 기록 문서

## 1. 현재 상태

현재 실행 경로는 `Qwen-Agent + transformers + stdin/stdout IPC`다.

이 구조에서 `Qwen-Agent`는 보조 레이어가 아니라 실제 판단 오케스트레이션의 기반이다.

정리하면:

- `Qwen-Agent`가 행동, 카드 교체, 대사, 회고의 오케스트레이션 중심이다.
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
  - 행동/교체/회고와 대사를 같은 Qwen-Agent 기반 런타임에서 처리하되, 대사만 별도 시스템 메시지와 짧은 사건 문맥을 쓴다.
- `tools.py`
  - `get_public_state`, `get_memory`, `get_recent_log`, `get_round_summary`
- `tasks.py`
  - 행동/교체/대사/회고 태스크 payload 조립
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

## 5. 대사 경로 메모

현재 대사 생성은 별도 raw completion 우회 경로가 아니라 `Qwen-Agent` 기반 경로를 유지한다.

- `agent.py`의 `generate_dialogue()`가 `build_dialogue_task()`를 호출한다.
- `tasks.py`는 최근 공개 로그를 그대로 붙이지 않고, 대사용 사건 문맥과 감정 힌트를 조립한다.
- `prompts.py`는 `상대에게 지금 바로 던지는 말` 중심의 프롬프트를 만든다.
- `runtime.py`는 `dialogue_agent`에 사야의 말투, 직접 화법, 금지 표현만 고정한 시스템 메시지를 준다.

즉 현재 대사 품질은 `Qwen-Agent를 뺀다/넣는다`보다, 대사용 사건 요약과 감정 힌트를 얼마나 잘 주느냐에 더 크게 좌우된다.
