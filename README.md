![LLMoker 배너](docs/seam_interp_prev_00001.gif)

# LLMoker

Ren'Py 기반 5드로우 포커 게임에 로컬 LLM NPC, 심리전 대사, ICRL 스타일 정책 업데이트를 결합한 프로젝트입니다.

## 현재 구현 상태

- 2인 5드로우 포커 규칙 구현
- 앤티 고정, 2회 베팅, 드로우, 쇼다운 흐름 구현
- `스크립트봇`과 `LLM NPC` 상대 지원
- LLM 행동 선택, 카드 교체 판단, 대사 생성 연결
- 라운드 종료 후 정책 회고도 LLM이 생성하고 다음 판단 문맥에 반영
- Qwen-Agent tool calling으로 공개 상태, 기억, 최근 로그, 라운드 요약을 조회
- 공개 정보와 비공개 정보 분리
- 메모리, 리플레이, 세이브를 SQLite로 관리
- 메인 메뉴와 포커 화면에 `webm` 영상 배경 적용
- 게임 UI는 한국어 기준으로 정리
- LLM 디버그용 터미널 로그 출력

## 영상 자산

- 현재 `main.webm`, `normal.webm`, `lost.webm`, `win.webm`는 `Wan 2.2` 기반으로 생성한 영상 자산이다.
- 메인 메뉴: `llmoker/game/gui/main.webm`
- 포커 기본 배경: `llmoker/game/images/minigames/normal.webm`
- 라운드 종료 시 플레이어 승리: `llmoker/game/images/minigames/lost.webm`
- 라운드 종료 시 NPC 승리: `llmoker/game/images/minigames/win.webm`
- 현재 GUI 기준 해상도는 `1024x576`이며, 영상과 포커 UI도 같은 비율로 축소해 표시합니다.
- 게임 시작은 검은 화면 없이 바로 `normal.webm`로 진입합니다.
- 라운드 종료 시에는 `lost.webm` 또는 `win.webm` 위에서 대사가 먼저 나오고, 그 다음 결과 패널이 열립니다.

## LLM NPC 요약

- 기본 상대 AI는 `LLM NPC`
- 로컬 모델은 `llmoker/models/llm/` 아래를 사용
- 현재 기본 모델 경로는 `backend/config.py`에서 결정
- `./5Drawminigame.sh`는 첫 실행 시 모델이 없으면 `Qwen/Qwen3-4B-Thinking-2507`를 자동 다운로드하려고 시도합니다.
- 자동 다운로드가 실패하면 같은 경로를 수동으로 받아 `llmoker/models/llm/qwen3-4b-thinking`에 배치하면 됩니다.
- 다운로드 경로: `https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507`
- LLM 워커는 `llmoker/.venv/bin/python`으로 별도 실행
- LLM 레이어는 `backend/llm/` 패키지로 분리
- LLM NPC 경로는 `Qwen-Agent + local transformers`로 고정
- Qwen-Agent 쪽 에이전트 타입은 `Assistant`를 사용
- 워커는 로컬 모델을 직접 로드하고, 네트워크 모델 서버를 거치지 않는다
- 기본 디바이스는 `auto`이며, CUDA가 보일 때만 GPU를 쓰고 아니면 CPU로 내린다
- 행동, 카드 교체, 대사, 정책 회고는 모두 `Qwen-Agent`의 tool calling 형식으로 처리
- 메인 메뉴 옵션은 `스크립트봇`과 `LLM NPC` 두 가지뿐이다
- 현재 구현은 LLM 실패 시 스크립트봇이나 안전 행동으로 숨기지 않고, 실패 원인을 그대로 표시한다
- `LLM NPC` 모드에서는 행동/드로우/대사 실패를 스크립트봇이나 안전 행동으로 숨기지 않습니다.
- `policy_loop`도 규칙 문자열이 아니라 LLM 정책 피드백을 우선 사용합니다.
- `policy_loop`는 라운드 종료 후 `Qwen-Agent`에 정책 회고를 요청하고, 그 결과를 SQLite 메모리에 저장합니다.
- 기본 모델 이름은 `Qwen3-4B-Thinking-2507`로 맞추고, 로컬 `transformers` 추론 설정으로 직접 로드합니다.
- 모델 원본 파일은 수정하지 않습니다.
- `qwen3-4b-thinking`는 사고 구간과 최종 응답을 분리해서 사용하며, 행동 JSON과 대사는 `</think>` 뒤 최종 출력만 읽습니다.
- 현재 연결된 도구는 `get_public_state`, `get_memory`, `get_recent_log`, `get_round_summary` 네 가지입니다.

중요:

- `Qwen-Agent`를 쓰려면 `qwen-agent`, `torch`, `transformers`가 필요합니다.
- `LLM NPC`는 로컬 워커가 모델을 직접 로드하므로, 모델 서버 연결 오류 대신 실제 모델 로딩 오류가 그대로 보입니다.

## 디버그 로그

게임 UI에서는 NPC 손패와 비공개 정보를 숨기지만, 터미널에는 아래 로그를 출력합니다.

- 라운드 시작 시 NPC 손패와 족보
- 베팅 시 허용 행동, 선택 행동, 이유
- 드로우 전후 손패와 교체 인덱스
- 라운드 종료 후 정책 피드백과 다음 전략 초점
- 쇼다운/폴드 종료 결과
- 대사 생성 결과

로그 형식:

```text
[LLMoker][DEBUG] ...
```

## 실행

프로젝트 루트:

```bash
cd LLMoker
```

게임 실행:

```bash
cd llmoker
./5Drawminigame.sh
```

자동 다운로드를 건너뛰고 직접 모델을 관리하려면:

```bash
cd llmoker
LLMOKER_SKIP_MODEL_DOWNLOAD=1 ./5Drawminigame.sh
```

개발용 자동 매치 테스트:

```bash
cd llmoker
python3 scripts/run_match.py
```

## 문서

- [블루프린트](docs/blueprint.md)
- [스타일 가이드](docs/styleguide.md)
- [LLM NPC 설정](docs/llm_npc_setup.md)
- [Qwen-Agent 구조](docs/qwen_agent.md)
- [대사 시스템](docs/dialogue_system.md)
- [ICRL 정책 업데이트](docs/icrl_policy_update.md)
- [Ren'Py 런타임 구조](docs/renpy_engine.md)

## 핵심 파일

- `llmoker/backend/poker_engine.py`
- `llmoker/backend/poker_hands.py`
- `llmoker/backend/script_bot.py`
- `llmoker/backend/llm/agent.py`
- `llmoker/backend/llm/prompts.py`
- `llmoker/backend/llm/worker_client.py`
- `llmoker/backend/llm/runtime_worker.py`
- `llmoker/scripts/run_match.py`
- `llmoker/game/poker_minigame.rpy`
- `llmoker/game/poker_ui.rpy`
- `llmoker/game/poker_dialogue.rpy`

## 현재 주의사항

- `LLM NPC`는 `Qwen-Agent + local transformers` 전제가 충족되어야만 정상 동작합니다.
- Ren'Py UI에 예외 문자열을 올릴 때는 `{}` 같은 태그 문자를 이스케이프해야 합니다.
- SQLite는 Ren'Py 본체가 직접 사용하므로 `.venv`가 아니라 `vendor/` 경로를 사용합니다.
