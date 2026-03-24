# LLM 서빙 구조

## 1. 결론

현재 배포용 LLM 런타임은 `Qwen-Agent + transformers` 기반이며, `stdin/stdout IPC`로 붙는다.

여기서 `Qwen-Agent`는 옵션이 아니라 기반 오케스트레이션 계층이고, `transformers`는 그 아래에서 실제 모델 추론을 담당한다.

- 기본 모델: `llmoker/models/llm/qwen3-4b-instruct-2507`
- 자동 다운로드: `Qwen/Qwen3-4B-Instruct-2507`
- 실제 실행 경로: `backend/llm/client.py` -> `backend/llm/runtime.py`

기존 `vLLM` 서버-클라이언트 구조는 공부용으로 남겨 두고, 현재 실행 경로에서는 쓰지 않는다.

- 백업 위치: `llmoker/backend/llm/vllm_backup/`

## 2. 왜 vLLM에서 transformers로 바꿨는가

Steam 같은 일반 유저 배포 기준에서는 `vLLM`보다 `transformers`가 유리하다.

- 별도 HTTP 모델 서버를 또 띄울 필요가 없다.
- 포트 충돌, 로컬 방화벽 예외, `Ctrl+C` 후 서버 잔류 같은 운영 문제가 줄어든다.
- CUDA GPU가 없는 환경에서도 CPU로 최소 실행은 가능하다.
- 유저 PC마다 다른 드라이버, VRAM, 백그라운드 상태에 덜 민감하다.
- 단일 유저 게임은 동시 요청 처리량보다 "실행하면 바로 된다"가 더 중요하다.

정리하면:

- `vLLM`
  - 빠를 수 있다.
  - 대신 배포와 지원 비용이 커진다.
- `transformers`
  - 더 단순하다.
  - 배포 안정성이 더 낫다.

## 3. 현재 실행 흐름

현재 게임 실행 시 LLM 경로는 아래처럼 돈다.

1. `llmoker/5Drawminigame.sh`
   - 모델 다운로드만 먼저 확인한다.
2. `llmoker/backend/llm/client.py`
   - 게임 프로세스 안에서 Python 3.11 `.venv` 런타임을 자식 프로세스로 띄운다.
   - 요청은 `stdin`, 응답은 `stdout`으로 주고받는다.
3. `llmoker/backend/llm/runtime.py`
   - `transformers`로 토크나이저와 모델을 직접 로드한다.
   - 그 위에 `Qwen-Agent FnCallAgent`를 올려 tool calling 기반으로 행동, 교체, 대사, 회고를 처리한다.
   - 준비가 끝나면 한 줄 JSON으로 ready 상태를 내보낸다.
   - 이후 한 줄 JSON 요청을 읽어 바로 결과를 돌려준다.
4. `llmoker/backend/llm/agent.py`
   - 포커 엔진이 쓰는 상위 어댑터다.
   - 행동, 카드 교체, 대사, 회고 요청을 런타임으로 보낸다.

즉 현재 구조는 `Ren'Py 3.9`와 `.venv 3.11` ABI 차이를 넘기기 위한 최소 외부 런타임만 유지하되, HTTP 서버는 쓰지 않는다.

## 4. 현재 런타임이 처리하는 작업

런타임은 아래 네 가지 작업만 처리한다.

- 행동 선택
- 카드 교체 판단
- 심리전 대사 생성
- 라운드 회고 및 전략 업데이트

행동, 카드 교체, 회고는 `Qwen-Agent`가 도구를 통해 공개 상태를 확인한 뒤 JSON 결과를 낸다.
대사는 `Qwen-Agent`가 최근 공개 사건을 확인한 뒤 캐릭터 대사 한두 줄을 낸다.

## 5. 백업 정책

기존 `vLLM` 코드는 바로 지우지 않고 아래에 백업한다.

- `llmoker/backend/llm/vllm_backup/client.py`
- `llmoker/backend/llm/vllm_backup/runtime.py`

이 백업은 현재 실행 경로가 아니라, 이전 `vLLM` 서버-클라이언트 구조를 참고하기 위한 보관본이다.

## 6. 배포 관점 주의사항

- 일반 유저 배포판은 `transformers` 기준으로 유지한다.
- `vLLM`은 실험용이나 개인 환경 최적화용으로만 다시 검토한다.
- 로컬 모델이 없으면 `5Drawminigame.sh`가 먼저 다운로드를 시도한다.
- 새 게임 시작 시 기억은 초기화되고, 세이브를 저장했을 때만 기억 스냅샷이 같이 복원된다.
