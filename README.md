![LLMoker 배너](docs/seam_interp_prev_00001.gif)

# LLMoker

Ren'Py 기반 5드로우 포커 게임에 로컬 LLM NPC, 행동/단계 시스템 나레이션, LLM 기반 정책 회고를 결합한 프로젝트입니다.

## 현재 구현 상태

- 2인 5드로우 포커 규칙 구현
- 앤티 고정, 2회 베팅, 드로우, 쇼다운 흐름 구현
- `스크립트봇`과 `LLM NPC` 상대 지원
- LLM 행동 선택, 카드 교체 판단, 대사 생성 연결
- 라운드 종료 후 정책 회고도 LLM이 생성하고 다음 판단 문맥에 반영
- 게임 레벨 작업은 `backend/llm/tasks.py`에서 행동 선택, 카드 교체 판단, 심리전 대사 생성, 라운드 회고로 명시적으로 분리
- 공개 정보와 비공개 정보 분리
- 메모리, 리플레이, 세이브를 SQLite로 관리
- 메인 메뉴와 포커 화면에 `webm` 영상 배경 적용
- 게임 UI는 한국어 기준으로 정리
- LLM 디버그용 터미널 로그 출력

## 영상 자산

- 현재 `main.webm`, `normal.webm`, `lost.webm`, `win.webm`는 `Wan 2.2` 기반으로 생성한 영상 자산이다.
- 메인 메뉴는 좌측 패널과 우측 타이틀을 나눈 카지노 네온 분위기 레이아웃으로 커스텀한다.
- 메인 메뉴는 슬로건이나 군더더기 없이 `LLMoker` 타이틀 자체가 중심이 되도록 유지한다.
- 메인 메뉴: `llmoker/game/gui/main.webm`
- 포커 기본 배경: `llmoker/game/images/minigames/normal.webm`
- 라운드 종료 시 플레이어 승리: `llmoker/game/images/minigames/lost.webm`
- 라운드 종료 시 NPC 승리: `llmoker/game/images/minigames/win.webm`
- 현재 GUI 기준 해상도는 `1024x576`이며, 영상과 포커 UI도 같은 비율로 축소해 표시합니다.
- 게임 시작은 검은 화면 없이 바로 `normal.webm`로 진입합니다.
- 라운드 종료 시에는 `lost.webm` 또는 `win.webm` 위에서 대사가 먼저 나오고, 그 다음 결과 패널이 열립니다.

## 오디오 자산

- 메인 메뉴 BGM: `llmoker/game/audio/main.flac`
- 포커 게임 BGM: `llmoker/game/audio/game.flac`
- 메인 메뉴와 포커 화면은 같은 `music` 채널을 공유하고, 화면 전환 시점에 곡을 바꿉니다.
- 현재 음악 자산 제작에는 `ACE-Step`을 사용했습니다.
- 현재 음성/TTS 자산 제작 기록은 `CosyVoice` 기준으로 관리합니다.

## 제작 파이프라인

- 영상 생성: `Wan 2.2`
- 음악 생성: `ACE-Step`
- TTS/보이스 생성: `CosyVoice`
- 게임 QA 및 코드 검수: `Codex`, `Claude Code`

위 항목은 “현재 저장소에서 실제 런타임에 쓰는 모델”과는 별개로, 자산 제작과 QA 과정에서 사용한 도구를 기록한 것입니다.

## LLM NPC 요약

- 기본 상대 AI는 `LLM NPC`
- 로컬 모델은 `llmoker/models/llm/` 아래를 사용
- 현재 기본 모델 경로는 `backend/config.py`에서 결정
- 현재 기본 런타임 모델은 `llmoker/models/llm/qwen3-4b-instruct-2507`입니다.
- `./5Drawminigame.sh`는 첫 실행 시 모델이 없으면 `Qwen/Qwen3-4B-Instruct-2507`를 자동 다운로드하려고 시도합니다.
- `./5Drawminigame.sh`는 clone 직후 `.venv`가 없으면 먼저 `llmoker/.venv`를 생성합니다.
- `.venv`에 `pip`가 없으면 `ensurepip`로 먼저 복구합니다.
- 필수 런타임 패키지(`qwen-agent`, `torch`, `transformers` 등)가 없으면 `requirements.txt` 기준으로 자동 설치를 시도합니다.
- 자동 다운로드가 실패하면 같은 경로를 수동으로 받아 `llmoker/models/llm/qwen3-4b-instruct-2507`에 배치하면 됩니다.
- 다운로드 경로: `https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507`
- LLM 런타임은 `llmoker/.venv/bin/python`으로 별도 실행
- LLM 레이어는 `backend/llm/` 패키지로 분리
- LLM NPC 경로는 `transformers` 기반 외부 런타임으로 고정
- 런타임은 로컬 모델을 직접 로드하고, 별도 vLLM 서버를 띄우지 않는다
- 기본 디바이스는 `auto`이며, CUDA가 보일 때만 GPU를 쓰고 아니면 CPU로 내린다
- 행동, 카드 교체, 정책 회고는 모두 같은 transformers 런타임에서 처리
- 메인 메뉴 옵션은 `스크립트봇`과 `LLM NPC` 두 가지뿐이다
- 현재 구현은 LLM 실패 시 스크립트봇이나 안전 행동으로 숨기지 않고, 실패 원인을 그대로 표시한다
- `LLM NPC` 모드에서는 행동/드로우/대사 실패를 스크립트봇이나 안전 행동으로 숨기지 않습니다.
- `policy_loop`도 규칙 문자열이 아니라 LLM 정책 피드백을 우선 사용합니다.
- `policy_loop`는 라운드 종료 후 런타임에 정책 회고를 요청하고, 그 결과를 SQLite 메모리에 저장합니다.
- 기본 모델 이름은 `Qwen3-4B-Instruct-2507`로 맞춥니다.
- 모델 원본 파일은 수정하지 않습니다.
- `Qwen3-4B-Instruct-2507`를 기본 런타임 모델로 사용하며, 행동 JSON과 대사는 최종 출력 문자열만 읽습니다.
- 태스크별 생성 상한은 문맥 길이와 JSON 안정성을 함께 고려해 유지합니다. 현재 기준으로 행동/드로우는 `64`, 대사는 `80`, 정책 회고는 `384` 토큰입니다.
- 게임 레벨 태스크는 `행동 선택`, `카드 교체 판단`, `라운드 회고 및 전략 업데이트` 세 가지입니다.

중요:

- 현재 로컬 런타임 기준 필수 패키지는 `numpy`, `pydantic`, `pydantic-core`, `python-dateutil`, `qwen-agent`, `soundfile`, `torch`, `transformers`입니다.
- `LLM NPC`는 로컬 Qwen 런타임이 모델을 직접 로드하므로, 모델 서버 연결 오류 대신 실제 모델 로딩 오류가 그대로 보입니다.

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

다른 컴퓨터에서 `git clone` 후 바로 실행해야 한다면, Ren'Py 플랫폼 파일이 `llmoker/lib/` 아래에 실제로 포함되어 있어야 합니다.
현재 배포 기준으로는 `llmoker/lib/`가 Git 관리 대상이어야 하며, clone 후 `Ren'Py platform files not found`가 뜨면 체크해야 할 건 `.venv`가 아니라 `llmoker/lib/` 존재 여부입니다.

이미 다른 Ren'Py SDK나 같은 버전 게임 설치본이 있다면 아래로 복구할 수 있습니다.

```bash
cd llmoker
./after_checkout.sh /path/to/renpy-project-or-sdk
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

게임을 켜지 않고 런타임 태스크를 확인하려면:

```bash
cd llmoker
./.venv/bin/python scripts/check_qwen_agent.py
```

모델 자체 raw 응답만 확인하려면:

```bash
cd llmoker
./.venv/bin/python scripts/check_raw_inference.py --mode dialogue
```

## 문서

- [블루프린트](docs/blueprint.md)
- [스타일 가이드](docs/styleguide.md)
- [LLM NPC 설정](docs/llm_npc_setup.md)
- [LLM 서빙 구조](docs/serving.md)
- [Qwen-Agent 구조](docs/qwen_agent.md)
- [오디오 구조](docs/audio.md)
- [대사 시스템](docs/dialogue_system.md)
- [ICRL 정책 업데이트](docs/icrl_policy_update.md)
- [Ren'Py 런타임 구조](docs/renpy_engine.md)

## 핵심 파일

- `llmoker/backend/poker_engine.py`
- `llmoker/backend/poker_hands.py`
- `llmoker/backend/script_bot.py`
- `llmoker/backend/llm/agent.py`
- `llmoker/backend/llm/client.py`
- `llmoker/backend/llm/runtime.py`
- `llmoker/backend/llm/tasks.py`
- `llmoker/backend/llm/prompts.py`
- `llmoker/scripts/run_match.py`
- `llmoker/game/poker_minigame.rpy`
- `llmoker/game/poker_ui.rpy`
- `llmoker/game/poker_dialogue.rpy`

## 현재 주의사항

- `LLM NPC`는 Python 3.11 transformers 런타임을 별도 프로세스로 실행하는 구조를 전제로 합니다.
- GPU가 있으면 `cuda`, 없으면 `cpu`로 내려가며, `vLLM`처럼 CUDA가 없다고 바로 시작 단계에서 막히지는 않습니다.
- Ren'Py UI에 예외 문자열을 올릴 때는 `{}` 같은 태그 문자를 이스케이프해야 합니다.
- SQLite는 Ren'Py 본체가 직접 사용하므로 `.venv`가 아니라 `vendor/` 경로를 사용합니다.
- 게임 시작 전 런타임 예열이 실패하면 자세한 오류는 `llmoker/data/logs/qwen_runtime_start.log`에 남깁니다.
