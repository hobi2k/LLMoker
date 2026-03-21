# LLMoker 블루프린트

## 1. 프로젝트 개요

Ren'Py 런타임 구조와 `vendor/` 사용 이유는 [renpy_engine.md](docs/renpy_engine.md)에 별도로 정리한다.
대사 이벤트 훅과 현재 LLM 대사 연결 구조는 [dialogue_system.md](docs/dialogue_system.md)에 별도로 정리한다.
현재 LLM NPC 연결 방식과 `qwen3-4b-thinking` 모델 사용 구조는 [llm_npc_setup.md](docs/llm_npc_setup.md)에 별도로 정리한다.
`Qwen-Agent` 레이어의 파일 역할과 폴더 구조 이유는 [qwen_agent.md](docs/qwen_agent.md)에 별도로 정리한다.
ICRL을 `파인튜닝`이 아니라 `문맥 내 행동 정책 업데이트`로 해석하는 기준은 [icrl_policy_update.md](docs/icrl_policy_update.md)에 별도로 정리한다.
코드 작성 스타일과 독스트링 기준은 [styleguide.md](docs/styleguide.md)에 별도로 정리한다.
LLM 의존성 관리는 루트 `requirements.txt`, 루트 `pyproject.toml`, `llmoker/pyproject.toml`에 같이 반영한다.

LLMoker는 다음 요소를 결합하는 LLM 기반 게임 프로젝트다.

- Ren'Py 비주얼노벨 프레임워크
- 5 Card Draw 포커 미니게임
- LLM 기반 상대 AI
- 캐릭터 대사, 성격, 블러핑, 관계도 연출

이 프로젝트의 핵심은 게임을 처음부터 만드는 것이 아니라, 준비된 미니게임 자산 위에 `정확한 포커 엔진 + LLM 에이전트 + 캐릭터 연출 레이어`를 얹는 것이다.

이 방향이 좋은 이유는 분명하다.

- 하스스톤류 카드게임보다 룰이 단순하다.
- 숨겨진 정보가 있어서 LLM 판단이 의미 있다.
- 행동 종류가 적어 프롬프트 설계가 안정적이다.
- Ren'Py와 결합했을 때 캐릭터성과 대사 연출이 자연스럽다.

LLM NPC 설계의 핵심 제약은 아래와 같다.

- LLM NPC는 플레이어의 손패를 볼 수 없다.
- LLM NPC와 플레이어가 공통으로 보는 정보는 공개 베팅/체크/레이즈/폴드/카드 교체 수 같은 공개 행동 정보뿐이다.
- LLM NPC는 대화로 심리전을 걸 수 있다.
- LLM NPC는 결과와 피드백을 바탕으로 in-context reinforcement learning 방식으로 행동 정책과 대사 정책을 수정할 수 있다.
- 이때 라운드 회고와 다음 전략 초점도 LLM이 직접 생성해야 한다. 규칙 기반 회고는 `스크립트봇` 경로에만 남긴다.

## 1.1 현재 구현 요약

지금 저장소 기준으로 이미 구현되어 있는 핵심 기능은 아래와 같다.

- Ren'Py 메인 메뉴와 공용 메뉴 한국어화
- 메인 메뉴 배경 `game/gui/main.webm` 적용
- 포커 기본 배경 `game/images/minigames/normal.webm` 적용
- 라운드 종료 시 승패별 `win.webm`, `lost.webm` 배경 전환
- 위 `webm` 영상 자산은 `Wan 2.2` 기반 생성본을 사용
- 현재 GUI 기준 해상도는 `1024x576`이며, 영상과 포커 UI를 같은 비율로 축소해 사용
- 정통 5드로우에 가까운 `체크 / 베팅 / 콜 / 레이즈 / 폴드 / 드로우` 흐름
- 스크립트봇과 LLM NPC 전환 지원
- LLM 행동 선택, 카드 교체, 대사 생성 연결
- 라운드 종료 후 정책 피드백과 다음 전략 초점도 LLM이 생성
- 위 네 흐름은 모두 `Qwen-Agent` tool calling으로 공개 상태와 기억을 조회하면서 처리
- 대사 이벤트 훅은 유지하되, `LLM NPC` 모드 실패를 스크립트 대사로 숨기지 않는다.
- memory / replay / save SQLite 저장
- 터미널 디버그 로그로 NPC 비공개 손패와 행동 판단 확인 가능
- LLM NPC 경로는 `Qwen-Agent(local transformers)` 하나로 고정
- Qwen-Agent 쪽 에이전트 타입은 `Assistant`로 유지
- 메인 메뉴에서 고를 수 있는 상대 AI는 `LLM NPC`와 `스크립트봇` 두 가지뿐이다
- LLM NPC 실패 시 자동 폴백 없이 명시적 실패 상태를 유지한다
- `qwen3-4b-thinking`는 사고 구간과 최종 응답을 분리해 사용하고, 행동/드로우/대사 해석은 `</think>` 뒤 최종 응답만 기준으로 한다.
- 로컬 모델 폴더 내부 파일은 수정하지 않는다.

## 2. 2026년 3월 19일 기준 폴더 구조

현재 `LLMoker` 저장소의 실제 구조를 기준으로 보면 핵심은 아래와 같다.

```text
LLMoker/
├── .gitignore
├── pyproject.toml
├── README.md
├── LICENSE
├── docs/
│   ├── blueprint.md
│   ├── renpy_engine.md
│   ├── dialogue_system.md
│   ├── llm_npc_setup.md
│   └── icrl_policy_update.md
└── llmoker/
    ├── 5Drawminigame.sh
    ├── 5Drawminigame.py
    ├── 5Drawminigame.exe
    ├── main.py
    ├── pyproject.toml
    ├── README.md
    ├── log.txt
    ├── traceback.txt
    ├── game/
    │   ├── script.rpy
    │   ├── poker_minigame.rpy
    │   ├── gui/
    │   ├── images/
    │   ├── tl/
    │   ├── cache/
    │   └── saves/
    ├── lib/
    │   ├── py3-linux-x86_64/
    │   ├── py3-windows-x86_64/
    │   └── python3.9/
    ├── vendor/
    │   ├── pysqlite3/
    │   └── pysqlite3_binary.libs/
    ├── renpy/
    │   ├── common/
    │   ├── display/
    │   ├── text/
    │   ├── audio/
    │   └── ...
    └── .venv/
```

### 각 경로의 의미

- `LLMoker/`
  - 저장소 루트다. 기획 문서, 루트 `pyproject.toml`, 루트 `.gitignore`를 두는 기준 위치다.
- `LLMoker/llmoker/`
  - 실제 Ren'Py 실행 프로젝트 루트다.
- `LLMoker/llmoker/game/`
  - 게임 스크립트, 이미지, UI, 저장 데이터가 들어가는 핵심 폴더다.
- `LLMoker/llmoker/game/script.rpy`
  - 시작 라벨이 있는 진입 파일이다.
- `LLMoker/llmoker/game/poker_minigame.rpy`
  - 현재 포커 미니게임 로직이 구현된 핵심 파일이다.
- `LLMoker/llmoker/lib/`
  - 플랫폼별 실행 바이너리와 런타임이 들어 있다.
- `LLMoker/llmoker/renpy/`
  - Ren'Py 엔진 자체 코드다. 프로젝트 로직은 가능하면 여기보다 `game/` 아래에 두는 편이 맞다.

## 3. 현재 목표 폴더 구조

현재 구현과 이후 확장 기준을 함께 만족하는 표준 구조는 아래와 같다.

```text
LLMoker/
├── .gitignore
├── pyproject.toml
├── docs/
│   └── blueprint.md
└── llmoker/
    ├── renpy/
    │   ├── common/
    │   ├── display/
    │   ├── text/
    │   ├── audio/
    │   └── ...
    ├── game/
    │   ├── script.rpy
    │   ├── poker_minigame.rpy
    │   ├── poker_core.rpy
    │   ├── poker_agents.rpy
    │   ├── poker_ui.rpy
    │   ├── poker_dialogue.rpy
    │   ├── poker_config.rpy
    │   ├── images/
    │   │   └── minigames/
    │   ├── gui/
    │   └── saves/
    ├── lib/
    ├── vendor/
    ├── main.py
    ├── backend/
    │   ├── config.py
    │   ├── poker_engine.py
    │   ├── poker_hands.py
    │   ├── script_bot.py
    │   ├── memory_manager.py
    │   ├── replay_logger.py
    │   ├── save_state_store.py
    │   └── llm/
    │       ├── agent.py
    │       ├── prompts.py
    │       ├── results.py
    │       ├── tools.py
    │       ├── worker_client.py
    │       └── runtime_worker.py
    └── pyproject.toml
```

### 권장 파일 역할

- `script.rpy`
  - 게임 시작, 메인 메뉴 이후 흐름, 시나리오 진입점
- `renpy/`
  - Ren'Py 엔진 런타임 폴더다. 일반적으로 직접 수정 대상은 아니며, 프로젝트 게임 로직은 `game/` 아래에 두는 것을 원칙으로 한다.
- `lib/`
  - 플랫폼별 실행 바이너리와 파이썬 런타임이 들어 있는 배포 폴더다.
- `vendor/`
  - Ren'Py 번들 파이썬에 기본 포함되지 않은 의존성을 넣는 폴더다. 현재는 SQLite 사용을 위해 `pysqlite3-binary`를 여기서 로드한다.
- `models/llm/`
  - 로컬 LLM 모델 폴더다. 현재 기본 대상 모델은 `qwen3-4b-thinking`다. 공식 소스는 `https://huggingface.co/Qwen/Qwen3-4B-Thinking-2507`이며, 다른 모델로 바꾸려면 `backend/config.py`의 기본 경로 또는 `LOCAL_LLM_PATH`를 수정한다.
- `backend/poker_hands.py`
  - 카드 표현, 덱 생성, 족보 평가처럼 포커 규칙 공용 로직을 분리한 파일이다.
- `backend/script_bot.py`
  - LLM이 꺼져 있어도 완전한 한 판을 진행할 수 있는 규칙 기반 상대를 둔 파일이다.
- `backend/llm/`
  - Qwen-Agent 레이어를 모아 둔 폴더다.
  - 여기서 `agent.py`는 엔진 어댑터, `prompts.py`는 프롬프트, `tools.py`는 tool calling 노출면, `worker_client.py`는 서버와 워커 관리, `runtime_worker.py`는 실제 워커 실행 진입점을 맡는다.
- `scripts/`
  - 개발용 보조 스크립트만 둔다.
  - 현재는 `run_match.py`처럼 CLI 테스트용 파일만 여기에 둔다.
- `poker_minigame.rpy`
  - 실제 라벨 흐름과 화면 전환의 메인 진입점
- `poker_core.rpy`
  - 덱, 핸드 평가, 베팅 상태, 승패 판정
- `poker_agents.rpy`
  - 인간 입력 어댑터, 스크립트 봇, LLM 에이전트
- `poker_ui.rpy`
  - 카드 선택, 베팅 버튼, 로그 표시, 결과창
- `poker_dialogue.rpy`
  - 캐릭터 대사, 표정, 블러프 반응, 관계도 이벤트
- `poker_config.rpy`
  - 스택 크기, 앤티, 모델 설정, 디버그 옵션

### 현재 UI 규칙

플레이 도중 필요한 정보와 라운드 종료 정보는 명확히 구분해야 한다.

- 플레이 중 상시 HUD는 우상단에 `페이즈 / 팟 / 칩 현황 / 현재 족보`만 표시한다.
- 베팅 라운드 UI는 현재 합법 행동만 버튼으로 노출한다.
- 최근 진행 로그는 상시 패널로 띄우지 않고 하단 `로그 보기` 버튼으로만 확인한다.
- 라운드 종료 화면에서는 플레이어와 상대의 손패 이미지를 동시에 공개한다.
- 라운드 종료 화면의 카드 비교는 `상대 패 상단 / 플레이어 패 하단`의 세로 구조로 배치한다.
- 라운드 종료 화면에서는 `승리/패배/무승부`, `각자 족보`, `현재 스택`, `팟 획득 결과`를 한눈에 보여줘야 한다.
- 다음 라운드가 가능한지, 아니면 한쪽 스택 부족으로 매치가 끝났는지도 종료 화면에 반드시 표시해야 한다.
- 메인 메뉴 이동은 `screen Return()` 뒤의 `label return`에 의존하지 않고, `MainMenu` 액션이나 `jump main_menu`로 직접 처리한다.
- Ren'Py 스크립트에서는 `_`를 임시 변수명으로 사용하지 않는다. `_`는 번역 함수로 쓰이므로 덮어쓰면 `screens.rpy` 공용 UI가 깨질 수 있다.
- 백엔드 예외 문자열을 Ren'Py `text`에 그대로 넣을 때는 `{}` 같은 태그 문자를 이스케이프해서 UI가 죽지 않게 한다.

핵심 원칙은 이렇다.

- Ren'Py는 연출과 화면을 담당한다.
- 포커 규칙 엔진은 진실의 원천이 된다.
- LLM은 행동 제안만 하고, 최종 판정 권한은 엔진이 가진다.
- `Qwen-Agent + local transformers` 레이어는 Ren'Py 본체와 분리된 프로세스 경계로 유지한다.
- 이 분리는 단순 취향이 아니라, Ren'Py 런타임과 로컬 모델 의존성을 직접 섞지 않기 위한 선택이다.
- 대사 시스템은 라운드 이벤트 훅 기반으로 붙인다. `스크립트봇` 모드는 규칙 기반 대사를 쓰고, `LLM NPC` 모드는 실패를 그대로 노출한다.
- 상대 AI는 메인 메뉴 `환경 설정`에서만 `스크립트봇`과 `LLM NPC` 사이를 전환할 수 있어야 한다.
- 기본 상대 AI는 `LLM NPC`로 두고, 필요할 때만 `스크립트봇`으로 내릴 수 있게 한다.

## 4. 백엔드 및 모델 폴더 구조

지금 문서에서 가장 빠져 있던 부분이 이거다. `LLM을 붙인다`고만 하면 안 되고, 실제로 `모델 파일`, `백엔드 코드`, `학습 산출물`, `설정 파일`을 어디에 둘지 정해야 한다.

현재 `llmoker/main.py`와 `llmoker/pyproject.toml`를 보면 백엔드 패키지는 아직 비어 있는 상태에 가깝다. 따라서 아래처럼 `llmoker/` 아래에 명시적으로 백엔드 영역을 만드는 편이 맞다.

### 4.1 권장 백엔드 구조

```text
LLMoker/
└── llmoker/
    ├── game/
    ├── renpy/
    ├── lib/
    ├── backend/
    │   ├── config.py
    │   ├── poker_engine.py
    │   ├── memory_manager.py
    │   ├── policy_loop.py
    │   ├── replay_logger.py
    │   └── llm/
    │       ├── agent.py
    │       ├── prompts.py
    │       ├── results.py
    │       ├── tools.py
    │       └── worker_client.py
    ├── models/
    │   └── llm/
    ├── data/
    │   ├── prompts/
    │   ├── personas/
    │   ├── memory/
    │   ├── replays/
    │   ├── save/
    │   └── eval/
    ├── scripts/
    │   ├── run_match.py
    │   ├── run_self_play.py
    │   └── eval_agent.py
    ├── .env
    └── main.py
```

### 4.2 어떤 파일을 어디에 둬야 하는가

#### `backend/`

순수 파이썬 백엔드 로직을 두는 곳이다. 지금 프로젝트 범위에서는 폴더를 지나치게 쪼개기보다 핵심 모듈 몇 개로 유지하는 편이 낫다.

- 포커 규칙 엔진
- 상태 기계
- LLM 호출 코드
- 메모리 검색 및 반영
- 텍스트 기반 피드백을 다음 프롬프트에 반영하는 정책 루프

즉, `game/*.rpy`에서 직접 복잡한 로직을 다 처리하지 말고, 실제 계산은 여기서 하고 Ren'Py는 이 결과를 받아 화면에 뿌리는 구조가 맞다.

#### `models/`

로컬에서 사용하는 실제 모델 파일을 두는 곳이다. 질문에 대한 직접적인 답은 여기다.

권장 위치:

- 로컬 LLM 본체: `llmoker/models/llm/`

예시:

```text
llmoker/models/llm/qwen2.5-3b-instruct/
llmoker/models/llm/llama-3.1-8b-instruct/
```

`LoRA/adapter`, `tokenizer`를 별도 폴더로 나누는 구조는 이 프로젝트의 현재 목표에는 과하다. 일반적인 Hugging Face 로컬 모델은 모델 폴더 하나 안에 필요한 파일이 함께 들어 있으므로, 우선은 `models/llm/<model_name>/` 하나로 충분하다.

#### `data/`

모델 파일이 아닌 데이터 자산을 두는 곳이다.

- 프롬프트 템플릿
- 캐릭터 설정 JSON/YAML
- 장기 기억과 단기 기억 요약
- 대전 리플레이
- 평가 결과

### 4.3 모델 방식은 로컬 모델로 고정

이 프로젝트는 원격 API가 아니라 로컬 모델 사용을 전제로 한다. 따라서 문서와 구현 모두 아래 기준으로 맞춘다.

- 모델 가중치는 `llmoker/models/llm/` 아래에 둔다.
- 추론 상위 로직은 `backend/llm/agent.py`에서 담당한다.
- 프롬프트 구성은 `backend/llm/prompts.py`에서 담당한다.
- Qwen-Agent 도구 정의는 `backend/llm/tools.py`에서 담당한다.
- 워커 프로세스 관리는 `backend/llm/worker_client.py`에서 담당한다.
- 워커 실행 진입점은 `backend/llm/runtime_worker.py`에서 담당한다.
- 메모리와 피드백 반영은 `backend/memory_manager.py`, `backend/policy_loop.py`에서 담당한다.
- `backend/policy_loop.py`는 LLM 정책 리뷰 결과를 SQLite 메모리에 적재하는 경계 레이어다.
- LLM 워커 파이썬은 기본적으로 `llmoker/.venv/bin/python`을 사용한다.
- LLM NPC는 `Qwen-Agent + local transformers` 조합으로만 동작한다.
- Qwen-Agent에는 로컬 `transformers`에서 바로 먹는 샘플링 설정만 전달한다.
- 워커는 모델을 직접 로드하고, 별도 모델 서버를 자동 기동하지 않는다.
- 디바이스 힌트는 `auto`를 기본으로 두고, CUDA가 보일 때만 GPU를 사용한다.
- 행동, 드로우, 대사, 정책 회고는 모두 tool calling 형식으로 `get_public_state`, `get_memory`, `get_recent_log`, `get_round_summary`를 조회할 수 있어야 한다.
- 게임 UI에서는 LLM 백엔드를 따로 고르지 않는다.
- 로컬 워커가 기동하지 않거나 모델 로딩에 실패하면 LLM NPC는 실패 상태를 그대로 보여준다.
- 같은 실패 설정으로는 매 턴 재기동을 반복하지 않는다.
- 모델 원본은 수정하지 않는다.
- 게임 런처 `./5Drawminigame.sh`는 모델이 없으면 공식 Hugging Face 저장소에서 자동 다운로드를 먼저 시도한다.
- 자동 다운로드가 실패하면 공식 다운로드 경로와 배치 위치를 오류 문구로 안내한다.

현재 프롬프트 구성은 셋으로 나눈다.

- 행동 선택 프롬프트: `build_action_prompt(...)`
- 정책 피드백 프롬프트: `build_policy_feedback_prompt(...)`
- 대사 생성 프롬프트: `build_dialogue_prompt(...)`

현재 구현 상태는 아래와 같이 구분한다.

- 행동 선택 프롬프트는 LLM NPC 행동 선택 경로에 연결되어 있다.
- 정책 피드백 프롬프트는 라운드 종료 후 ICRL 메모리 갱신 경로에 연결되어 있다.
- 대사 생성 프롬프트는 대사 이벤트 호출부까지 연결되어 있다.
- 행동 선택과 카드 교체 판단은 공개 로그와 자기 손패만 사용한다.
- 정책 피드백 생성도 공개 로그와 라운드 결과만 사용한다.
- 대사 생성도 공개 로그와 결과 요약만 사용한다.
- 대사 생성 프롬프트는 플레이어에게 직접 말하는 2인칭 RP 대사 형식으로 강하게 제한한다.
- 플레이어 손패 정보는 LLM NPC 프롬프트에 포함하지 않는다.
- 게임 UI에는 비공개 정보를 숨기되, 터미널 디버그 로그에는 LLM NPC 손패와 행동 판단 과정을 출력해 개발 중 검증할 수 있게 한다.

즉, 모델 호출 구조는 항상 `models/llm/` + `backend/` 조합이다.

### 4.4 캐릭터 페르소나와 프롬프트는 어디에 두는가

이것도 모델과 섞으면 안 된다.

- 캐릭터 프로필: `llmoker/data/personas/`
- 시스템 프롬프트 템플릿: `llmoker/data/prompts/`
- 상황별 대사 템플릿: `llmoker/data/prompts/dialogue/`

예시:

```text
llmoker/data/personas/reina.json
llmoker/data/personas/yuna.json
llmoker/data/prompts/poker_action_system.txt
llmoker/data/prompts/dialogue/bluff_win.txt
```

### 4.5 기억은 어디에 두는가

이 프로젝트엔 기억이 반드시 들어가야 한다. 포커 행동만 반복하는 NPC는 금방 밋밋해진다. 기억은 전략과 캐릭터성을 동시에 강화한다.

권장 위치:

- 기억 DB: `llmoker/data/memory/memory.sqlite3`
- 리플레이 DB: `llmoker/data/replays/replays.sqlite3`
- 세이브 DB: `llmoker/data/save/game_state.sqlite3`

기억에 저장할 내용:

- 플레이어의 최근 베팅 습관
- 자주 블러프하는지에 대한 추정
- 이전 판의 인상적인 패배/승리
- 플레이어가 특정 캐릭터에게 했던 대사
- 관계도 변화의 근거 이벤트

즉, 다음 행동 프롬프트에는 현재 게임 상태만 넣는 것이 아니라 `현재 상태 + 최근 전략 피드백 + 기억 요약`을 같이 넣어야 한다.

### 4.6 SQLite 저장 구조

이 프로젝트는 memory, replay, save 상태를 모두 SQLite로 관리한다. 현재 구조에서는 JSONL보다 SQLite가 더 안정적이다.

권장 방향:

- memory 저장소: `llmoker/data/memory/memory.sqlite3`
- save 상태 저장소: `llmoker/data/save/game_state.sqlite3`
- 리플레이 저장소: `llmoker/data/replays/replays.sqlite3`
- SQLite 드라이버: `llmoker/vendor/pysqlite3/`

왜 SQLite가 좋은가:

- 세이브 가능한 상태를 한 곳에서 관리하기 쉽다.
- JSONL보다 조회와 갱신이 안정적이다.
- 플레이어 기억, 라운드 로그, 전략 피드백을 테이블로 분리할 수 있다.
- 런타임 객체와 세이브 스냅샷을 분리하기 좋다.
- Ren'Py 번들 파이썬에 `sqlite3`가 없는 환경에서도 `vendor/pysqlite3`로 강제 로드할 수 있다.

현재 저장 테이블 예시:

- `memory_entry`
- `round_replay`
- `save_state`

구현 원칙:

- `game/poker_config.rpy`와 `game/poker_core.rpy`에서 `vendor/`를 `sys.path` 앞쪽에 넣는다.
- `backend/sqlite_compat.py`에서 표준 `sqlite3` 대신 vendored `pysqlite3`를 우선 로드한다.
- `backend/memory_manager.py`, `backend/replay_logger.py`, `backend/save_state_store.py`는 모두 이 공용 드라이버만 사용한다.

런타임 경계는 아래처럼 고정한다.

- 일반 SQLite 저장 계층
  - Ren'Py 본체가 직접 사용한다.
  - 따라서 `.venv`가 아니라 `vendor + sqlite_compat`를 사용한다.
- LLM 추론 계층
  - `llmoker/.venv/bin/python`에서 실행한다.
  - `torch`, `qwen-agent`, `transformers`는 `.venv`에 설치한다.
- 향후 `sqlite-vec`를 붙일 경우
  - Ren'Py 본체가 직접 벡터 검색을 하면 `vendor` 경로를 검토한다.
  - LLM 백엔드 전용 벡터 검색이면 `.venv`에 두는 것을 기본으로 한다.

### 4.7 설정 파일은 어디에 두는가

설정도 문서에 명확히 써야 한다.

- API 키: `llmoker/.env`
- 파이썬 의존성: 루트 `pyproject.toml`
- 런타임 설정 로더: `llmoker/backend/config.py`

`.env` 예시:

```env
LOCAL_LLM_PATH=./models/llm/qwen2.5-3b-instruct
LLM_RUNNER_PYTHON=./.venv/bin/python
LLM_MODEL_NAME=qwen3-4b-thinking
LLM_MODEL_SERVER=http://127.0.0.1:8000/v1
LLM_API_KEY=EMPTY
MEMORY_DB_PATH=./data/memory/memory.sqlite3
REPLAY_DB_PATH=./data/replays/replays.sqlite3
SAVE_DB_PATH=./data/save/game_state.sqlite3
```

PyTorch는 현재 `cu130` 기준으로 설치한다.

```bash
./.venv/bin/python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu130
./.venv/bin/python -m pip install protobuf qwen-agent transformers
```

### 4.8 Ren'Py와 백엔드 연결 경계

역할 분리를 문서에 명시해야 한다.

- `game/*.rpy`
  - 화면 표시
  - 사용자 입력 처리
  - 캐릭터 대사 표시
- `backend/*`
  - 실제 포커 계산
  - LLM 추론 호출
  - 기억 검색 및 업데이트
  - 대전 피드백 누적
  - 저장/로그/평가

즉, `Ren'Py 화면 -> backend 서비스 호출 -> 결과 반환 -> 화면 갱신` 흐름으로 가야 한다.

### 4.9 최종 권장 결론

질문에 대한 가장 직접적인 답만 짧게 쓰면 아래다.

- 로컬 LLM 모델은 `llmoker/models/llm/`에 둔다.
- 프롬프트와 캐릭터 설정은 `llmoker/data/`에 둔다.
- 기억은 `llmoker/data/memory/`에 둔다.
- 루트 프로젝트 설정은 `LLMoker/pyproject.toml`, `LLMoker/.gitignore`에 둔다.
- 실제 백엔드 로직은 `llmoker/backend/`에 둔다.

## 5. 코드 작성 스타일 및 작업 규칙

이 섹션은 이후 구현 작업의 강제 기준이다. 앞으로 이 프로젝트에서 코드를 작성하거나 수정할 때는 반드시 이 섹션을 따른다.

### 5.1 docs/blueprint.md 참조 의무

- 이 문서는 LLMoker의 기준 설계 문서다.
- 이후 작업 시 항상 `docs/blueprint.md`를 먼저 참고하고, 구조와 역할 분리에 맞게 구현한다.
- 문서와 실제 코드 구조가 어긋나면 코드를 덮어쓰기 전에 문서와 코드 중 어느 쪽이 기준이어야 하는지 먼저 판단하고 둘을 다시 맞춘다.

### 5.2 작업 후 문서 업데이트 의무

- 코드 작성이나 구조 변경이 발생하면 작업 후 반드시 `docs/blueprint.md`를 업데이트한다.
- 업데이트 대상:
  - 폴더 구조가 바뀌었을 때
  - 역할 분리가 바뀌었을 때
  - 게임 규칙이 바뀌었을 때
  - LLM / memory / in-context RL 흐름이 바뀌었을 때
  - UI 구조가 바뀌었을 때
- 구현과 문서는 항상 같이 움직여야 한다.

### 5.3 역할 분리 규칙

- `game/*.rpy`
  - Ren'Py 라벨 흐름, 화면, 연출, 사용자 입력만 담당한다.
- `backend/*.py`
  - 포커 규칙, 상태 전이, 기억 처리, 리플레이 저장, 프롬프트 조합 같은 실제 로직을 담당한다.
- 새로운 기능을 추가할 때는 먼저 어느 레이어 책임인지 정하고 그 레이어에 넣는다.
- Ren'Py 파일에 과도한 게임 로직을 직접 넣지 않는다.

### 5.4 주석과 docstring 규칙

- 새로 작성하는 함수와 클래스에는 docstring을 반드시 남긴다.
- 기계적으로 찍은 템플릿형 docstring은 금지한다.
- 함수 설명 뒤에 `Args:`와 `Returns:`를 실제 내용과 함께 남긴다.
- `Args: 없음`, `Returns: 없음`, `함수명, ...` 같은 자동 생성 냄새가 나는 문구는 반복적으로 남발하지 않는다.
- 정말 필요한 정보만 짧고 자연스러운 한국어 문장으로 적는다.

```python
def example(arg1, arg2):
    """
    현재 상태를 읽어서 다음 행동 후보를 정리한다.

    Args:
        arg1: 현재 상태 객체다.
        arg2: 보조 설정 값이다.

    Returns:
        다음 단계에서 사용할 행동 후보 목록이다.
    """
```

- 클래스도 같은 원칙을 따른다.
- docstring은 한국어로 작성한다.
- 한 줄짜리 함수는 코드만으로 충분히 읽히면 docstring을 생략해도 된다.
- 코드만 봐도 명확한 단순 대입에는 주석을 달지 않는다.
- 규칙, 예외 처리, 상태 전이처럼 읽는 사람이 헷갈릴 수 있는 부분에는 짧은 주석을 남긴다.

### 5.5 네이밍 규칙

- 사용자에게 보이는 텍스트는 한국어로 작성한다.
- 내부 식별자와 파일명은 현재 저장소 구조를 따라 영어 기반 snake_case를 사용한다.
- Ren'Py 라벨명과 screen명도 일관된 이름을 사용한다.
- 상태 문자열은 가능한 한 한 군데에서 정의하고 재사용한다.

### 5.6 UI 작성 규칙

- 게임 내 사용자 노출 텍스트는 전부 한국어로 유지한다.
- 메인 메뉴와 공용 메뉴의 `환경 설정 / 도움말 / 정보 / 저장 / 불러오기 / 기록` 같은 기본 UI도 한국어로 유지한다.
- 기본 Ren'Py 대화창을 계속 띄우는 대신, 포커 화면은 HUD 중심으로 설계한다.
- 핵심 정보는 시야를 가리지 않는 위치에 둔다.
- 일러스트를 가리는 큰 제목, 중복 정보 패널, 불필요한 레이어는 넣지 않는다.
- 최근 진행 로그는 상시 패널로 고정하지 않고, 하단 `로그 보기`를 통해 필요할 때만 열 수 있게 한다.
- 저장 / 불러오기 / 환경 설정 / 메인 메뉴 같은 기본 조작은 화면에서 접근 가능해야 한다.
- 저장 기능을 위해 런타임 객체와 세이브용 상태 스냅샷을 분리한다.
- Ren'Py screen의 버튼 액션에서 부작용이 있는 함수 호출은 `SetVariable(func())` 형태로 직접 쓰지 않고 `Function(...)` 액션으로 호출한다.
- 상대 AI 모드 전환은 게임 도중 오버레이가 아니라 메인 메뉴 `환경 설정` 화면에서 변경하는 것을 기준으로 한다.
- 메인 메뉴 배경은 `llmoker/game/gui/main.webm` 루프 영상으로 표시한다.
- 포커 플레이 중 기본 배경은 `llmoker/game/images/minigames/normal.webm` 루프 영상으로 표시한다.
- 라운드 종료 화면에서는 플레이어 승리 시 `lost.webm`, NPC 승리 시 `win.webm`를 사용한다.
- 영상은 원본을 직접 재인코딩하지 않아도 Ren'Py 표시 단계에서 1920x1080으로 맞춰 보여준다.
- 게임 시작 시 검은 화면 없이 바로 `normal.webm` 배경으로 진입한다.
- 승패가 정해지면 해당 `win/lost.webm` 배경 위에서 대사가 먼저 진행되고, 그 다음 결과 화면을 연다.
- 게임 UI에는 상대 비공개 정보를 숨기고, 같은 내용은 터미널 디버그 로그에서만 확인한다.

### 5.7 현재 구현 규칙

- 현재 구현은 `스크립트봇`과 `LLM NPC`를 모두 지원해야 한다.
- 기본 상대는 `LLM NPC`다.
- 흐름:
  - 앤티
  - 카드 배분
  - 첫 번째 베팅
  - 드로우
  - 두 번째 베팅
  - 쇼다운
- LLM 경로는 행동 선택, 카드 교체 판단, 대사 생성까지 실제 연결된 상태를 유지한다.
- `LLM NPC` 모드에서는 실패 시 합법 행동이나 스크립트 대사로 숨기지 않고, 오류를 드러내서 먼저 해결하게 한다.
- 매치 시작 전처럼 아직 손패가 배분되지 않은 상태도 엔진과 프롬프트가 안전하게 처리해야 한다.

### 5.8 폴더 구조 준수 규칙

- 문서의 `현재 목표 폴더 구조`에 적힌 파일은 실제로 맞춰 둔다.
- 최소한 아래 파일들은 유지한다.
  - `game/poker_minigame.rpy`
  - `game/poker_core.rpy`
  - `game/poker_agents.rpy`
  - `game/poker_ui.rpy`
  - `game/poker_dialogue.rpy`
  - `game/poker_config.rpy`
- 백엔드와 데이터 폴더도 문서 기준 경로를 유지한다.

### 5.9 변경 전 체크리스트

새 작업을 시작하기 전에 아래를 확인한다.

1. 이 변경이 `game` 레이어인지 `backend` 레이어인지 구분했는가.
2. 현재 `docs/blueprint.md` 구조와 충돌하지 않는가.
3. 사용자 노출 텍스트가 한국어인가.
4. 새 함수와 클래스에 docstring을 남길 준비가 되어 있는가.

### 5.10 변경 후 체크리스트

작업 후에는 아래를 확인한다.

1. 코드가 실제 폴더 구조와 맞는가.
2. 문서와 코드가 어긋나지 않는가.
3. 새 함수와 클래스에 docstring이 있는가.
4. 사용자가 보게 되는 텍스트가 한국어인가.
5. `docs/blueprint.md`에 반영해야 할 변화가 있다면 이미 반영했는가.

## 6. 왜 5 Card Draw가 적합한가

이 프로젝트에서 5 Card Draw를 선택하는 것은 매우 현실적이다.

### 이유

- 카드 수가 52장으로 고정이다.
- 각 플레이어의 핸드가 5장이라 상태 표현이 간결하다.
- 드로우 전/후, 두 번의 베팅 라운드만 있으면 된다.
- 정보 은닉이 존재하므로 추론, 확률, 블러핑이 살아난다.
- LLM이 `행동 + 이유 + 캐릭터 대사`를 동시에 생성하기 좋다.

즉, 룰은 단순하지만 전략성은 남아 있어서 LLM 실험과 게임 연출을 같이 보여주기 좋다.

## 7. 게임 비전

프로젝트의 최종 방향은 단순한 포커 시뮬레이터가 아니라, `캐릭터와 상호작용하는 포커 VN`이다.

예상 플레이 감각:

- 플레이어는 한 명의 캐릭터와 포커를 친다.
- 상대 캐릭터는 성격과 말투가 있다.
- 베팅 행동과 대사가 연결된다.
- 승패가 관계도, 감정 상태, 다음 장면에 영향을 준다.

확장 가능한 모드는 다음과 같다.

- `Player vs LLM`
- `LLM vs Scripted NPC`
- `LLM vs LLM`
- `Romance + Poker` 스토리 모드

## 8. 5 Card Draw 규칙 상세

이 섹션은 포커를 모르는 사람도 이해할 수 있도록 용어부터 설명한다. 튜토리얼, UI 문구, LLM 프롬프트 설명은 이 정의를 기준으로 맞춘다.

### 6.1 사용 덱

- 표준 52장 덱 사용
- 조커 없음
- 무늬: Hearts, Diamonds, Clubs, Spades
- 숫자: 2부터 10, Jack, Queen, King, Ace

### 6.2 목표

다음 중 하나로 팟을 가져오면 된다.

- 마지막 쇼다운에서 더 높은 족보를 만든다.
- 상대를 폴드하게 만든다.

여기서 `팟(pot)`은 이번 판에서 중앙에 걸린 칩 총합이다. 한 판이 끝나면 승자가 이 칩을 모두 가져간다.

### 6.3 라운드 시작 비용: 앤티 고정

이 프로젝트의 라운드 시작 비용은 블라인드가 아니라 앤티로 고정한다.

#### 앤티(Ante)

- 모든 플레이어가 라운드 시작 전에 같은 금액을 강제로 낸다.
- 예를 들어 2인 게임에서 앤티가 5이면, 플레이어와 NPC가 각각 5칩을 내고 시작한다.
- 그러면 첫 카드를 받기 전부터 팟은 10이 된다.

장점:

- 규칙 설명이 쉽다.
- 2인 미니게임에 잘 맞는다.
- 구현이 단순하다.

이 프로젝트에서 앤티를 고정하는 이유:

- 초심자 설명이 쉽다.
- Ren'Py UI를 단순하게 만들 수 있다.
- LLM에게 주는 상태 정보가 더 간단해진다.
- 2인 포커 데모를 빠르게 완성하기 좋다.

### 6.4 한 판의 진행 순서

정식 5 Card Draw 한 판은 아래 순서로 진행된다.

1. 각 플레이어가 고정 앤티를 낸다.
2. 각 플레이어에게 개인 카드 5장을 배분한다.
3. 첫 번째 베팅 라운드를 진행한다.
4. 드로우 단계에서 버릴 카드를 선택한다.
5. 버린 수만큼 새 카드를 뽑는다.
6. 두 번째 베팅 라운드를 진행한다.
7. 두 명 이상 남아 있으면 쇼다운을 진행한다.
8. 승자가 팟을 가져가고 다음 라운드로 넘어간다.

초심자용으로 풀어 쓰면 다음과 같다.

1. 시작 비용으로 앤티를 낸다.
   - 예: 각자 5칩씩 낸다.
2. 각자 카드 5장을 받는다.
   - 이 카드는 본인만 볼 수 있다.
3. 첫 번째 베팅을 한다.
   - 체크, 베팅, 콜, 레이즈, 폴드 중 상황에 맞는 행동을 고른다.
4. 카드 교체를 한다.
   - 필요 없는 카드를 버리고 같은 수만큼 새로 뽑는다.
5. 두 번째 베팅을 한다.
   - 드로우 이후 마지막 심리전 구간이다.
6. 둘 다 남아 있으면 카드를 공개한다.
   - 더 높은 족보가 승리한다.

### 6.5 베팅 라운드에서 가능한 행동

현재 베팅이 없는 경우:

- `check`
- `bet`

상대가 이미 베팅한 경우:

- `fold`
- `call`
- `raise`

현재 프로젝트 구현 기준:

- 앤티 고정
- 2인 헤즈업 5드로우
- 제한 베팅 구조
- 베팅 금액은 라운드당 고정 단위 `fixed_bet`
- 각 베팅 라운드의 레이즈 횟수는 `max_raises_per_round`로 제한

드로우 단계에서 가능한 행동:

- `stand_pat`
  - 카드를 하나도 바꾸지 않는다.
- `draw`
  - 바꿀 카드 인덱스 목록을 제출한다.

### 6.6 행동 뜻 설명

- `check`
  - 추가 칩을 내지 않고 턴을 넘긴다.
  - 단, 아직 누구도 베팅하지 않았을 때만 가능하다.
- `bet`
  - 이번 라운드에서 처음으로 칩을 거는 행동이다.
- `call`
  - 상대가 건 금액만큼 맞춰서 계속 가는 행동이다.
- `raise`
  - 상대가 건 금액보다 더 많이 올리는 행동이다.
  - 현재 구현에서는 `콜 금액 + 고정 베팅 단위`를 내는 제한 베팅 레이즈다.
- `fold`
  - 이번 판을 포기하는 행동이다. 이미 낸 칩은 돌려받지 못한다.
- `stand_pat`
  - 현재 손패를 유지하고 아무 카드도 바꾸지 않는다.
- `draw`
  - 일부 카드를 버리고 새 카드를 받는다.

### 6.7 포커 용어

- `pot`
  - 현재 중앙에 모인 칩 총량
- `stack`
  - 플레이어가 아직 보유한 칩
- `current_bet`
  - 해당 베팅 라운드에서 맞춰야 하는 최고 베팅액
- `to_call`
  - 현재 플레이어가 계속 가기 위해 추가로 내야 하는 금액
- `all_in`
  - 남은 칩 전부를 거는 행동

### 6.8 단순화 규칙

- 2인 플레이만 지원
- 고정 앤티 사용
- 사이드 팟 없음
- 베팅은 소수의 고정 선택지로 제한
- 드로우는 한 번만 허용
- 고정 시작 스택 사용

이 정도 구성이면 현재 프로젝트 범위에서 안정적으로 운영할 수 있다.

### 6.9 예시 라운드

예시:

1. 플레이어와 NPC가 각각 5칩 앤티를 낸다.
2. 팟은 10이 된다.
3. 서로 카드 5장씩 받는다.
4. 첫 번째 베팅 라운드에서 플레이어가 `bet 10`을 한다.
5. NPC가 `call`을 해서 팟은 30이 된다.
6. 플레이어는 카드 2장을 교체한다.
7. NPC는 카드 1장을 교체한다.
8. 두 번째 베팅 라운드에서 NPC가 `bet 20`을 한다.
9. 플레이어가 `call`한다.
10. 쇼다운에서 더 높은 족보를 가진 쪽이 팟 70을 가져간다.

## 9. 족보 규칙

족보 우선순위는 아래와 같다.

1. 로열 플러시
2. 스트레이트 플러시
3. 포카드
4. 풀하우스
5. 플러시
6. 스트레이트
7. 트리플
8. 투페어
9. 원페어
10. 하이카드

### 7.1 반드시 필요한 타이브레이커

현재 샘플 구현은 큰 족보 종류만 비교한다. 하지만 실제 게임용으로는 부족하다. 아래 비교가 반드시 들어가야 한다.

- 원페어
  - 페어 숫자를 먼저 비교하고, 같으면 남은 키커를 높은 순서대로 비교
- 투페어
  - 높은 페어, 낮은 페어, 마지막 키커 순으로 비교
- 트리플
  - 트리플 숫자 먼저 비교, 같으면 키커 비교
- 스트레이트
  - 가장 높은 카드 비교
- 플러시
  - 전체 5장 정렬 후 높은 카드부터 순차 비교
- 풀하우스
  - 트리플 숫자 먼저 비교, 그 다음 페어 숫자 비교

타이브레이커가 없으면 실제 승패 판정이 자주 틀어진다.

## 10. 현재 코드베이스 상태

현재 코드베이스에는 이미 다음 요소가 있다.

- 정통 5드로우 베팅 엔진
- 라운드 상태 기계
- 합법 행동 계산
- 카드 교체 처리
- 쇼다운 판정과 타이브레이커
- 스크립트봇과 LLM NPC 전환
- 공개 로그 기반 ICRL 메모리 루프
- LLM 대사 생성과 스크립트 폴백

즉, 현재 코드베이스는 확장 가능한 현재 기준 구현체다.

## 11. 목표 아키텍처


```text
Ren'Py UI / VN Layer
    |
    +-- 장면 전환
    +-- 대사 출력
    +-- 표정/캐릭터 연출
    +-- 버튼과 카드 선택
    |
Poker Match Controller
    |
    +-- 라운드 시작/종료
    +-- 페이즈 전환
    +-- 행동 적용
    +-- 합법 행동 검증
    +-- 쇼다운 처리
    |
Poker Engine
    |
    +-- 덱 관리
    +-- 핸드 평가
    +-- 드로우 처리
    +-- 스택/팟 계산
    +-- 승패 판정
    |
Agent Layer
    |
    +-- 인간 플레이어 입력
    +-- 스크립트 AI
    +-- LLM AI
    |
Model Gateway
    |
    +-- 로컬 모델 호출
    +-- 프롬프트 생성
    +-- JSON 응답 파싱
```

## 12. LLM 연동 방식

핵심 원칙은 간단하다.

- 포커 엔진이 진짜 게임 상태를 가진다.
- LLM은 자기에게 공개된 정보만 본다.
- LLM은 행동을 제안할 뿐이다.
- 컨트롤러가 최종 검증 후 실행한다.

### 10.1 LLM에게 전달할 입력

LLM은 자기 자리에서 볼 수 있는 정보만 받아야 한다.

예시:

```text
게임: 5 Card Draw Poker
페이즈: 첫 번째 베팅 라운드

당신은 Reina입니다.
성격: 도발적이고 침착하며 중간 정도로 공격적입니다.

당신의 손패:
- King of Spades
- Queen of Spades
- Queen of Diamonds
- 7 of Clubs
- 2 of Hearts

공개 정보:
- Pot: 50
- Your stack: 190
- Opponent stack: 210
- Bet to call: 10

가능한 행동:
- fold
- call
- raise 20
- raise 40

정확히 하나의 합법 행동만 선택하고 JSON으로만 응답하세요.
```

### 10.2 LLM 출력 형식

처음부터 구조화된 JSON으로 고정하는 편이 맞다.

베팅 예시:

```json
{
  "action": "raise",
  "amount": 20,
  "reason": "퀸 원페어로 현재 우위를 잡을 가능성이 높아 압박을 선택했다."
}
```

드로우 예시:

```json
{
  "action": "draw",
  "discard_indexes": [3, 4],
  "reason": "퀸 페어를 유지하고 약한 키커 두 장을 교체한다."
}
```

### 10.3 검증 규칙

LLM 응답은 절대 바로 실행하면 안 된다.

검증 순서:

1. JSON 파싱
2. 스키마 확인
3. 현재 상태에서 합법 행동인지 확인
4. 금액이 허용 범위인지 확인
5. 불법 응답이면 안전한 기본 행동으로 대체

안전한 기본값 예시:

- 상대 베팅이 있을 때 파싱 실패: `call` 가능 시 `call`, 아니면 `fold`
- 상대 베팅이 없을 때 파싱 실패: `check`
- 드로우 응답 실패: `stand_pat`

### 10.4 LLM 기반 NPC와 In-Context Reinforcement Learning

이 프로젝트는 `명시적인 모델 재훈련`보다 `텍스트 기반 전투 피드백을 다음 컨텍스트에 누적하는 방식`을 사용한다. 즉, PokeLLMon과 비슷하게 `in-context reinforcement learning`을 쓰는 방향으로 설계한다.

핵심 아이디어:

- 모델 가중치를 매번 다시 학습하지 않는다.
- 한 판이 끝날 때마다 피드백 텍스트를 만든다.
- 그 피드백을 다음 프롬프트에 반영한다.
- 반복 플레이를 통해 행동 생성 정책을 점진적으로 개선한다.

즉, 정책은 별도 `.pt` 파일이 아니라 `프롬프트 문맥 안에서 진화하는 행동 규칙`에 가깝다.

### 10.5 In-Context RL 루프

권장 루프는 아래와 같다.

1. 현재 게임 상태를 LLM에 전달한다.
2. LLM이 행동과 이유를 생성한다.
3. 포커 엔진이 행동의 합법성과 결과를 판정한다.
4. 라운드 종료 후 텍스트 피드백을 만든다.
5. 피드백을 캐릭터 메모리와 최근 전략 요약에 저장한다.
6. 다음 행동 프롬프트에 이 요약을 다시 넣는다.

형태로 쓰면:

`상태 -> 행동 생성 -> 결과 판정 -> 텍스트 피드백 생성 -> 메모리 업데이트 -> 다음 상태 프롬프트에 반영`

### 10.6 어떤 피드백을 누적할 것인가

피드백은 단순 승패보다 전략적 해석이 포함되어야 한다.

예시:

- "상대가 첫 베팅 라운드에서 자주 작은 베팅을 던진다."
- "약한 원페어에서 과도하게 콜해 칩 손실이 컸다."
- "드로우 이후 공격성이 높아질 때 블러프 성공률이 높았다."
- "플레이어는 큰 팟에서 보수적으로 접는 경향이 있다."
- "이번 판에서는 퀸 원페어로 레이즈했지만, 상대의 콜 패턴상 기대값이 낮았다."

이런 텍스트는 숫자형 보상보다 해석 가능성이 높고, 캐릭터형 NPC에도 잘 맞는다.

### 10.7 기억과 In-Context RL의 결합

이 프로젝트에서는 `기억`이 사실상 in-context RL의 저장 장치 역할을 한다.

구분은 이렇게 잡는 편이 좋다.

- 단기 기억
  - 최근 몇 핸드의 행동 패턴
  - 방금 전 라운드의 성공/실패 피드백
  - 직전 심리전 결과
- 장기 기억
  - 플레이어의 장기적 스타일 추정
  - 캐릭터 관계 변화
  - 반복적으로 관측된 전략 패턴

다음 프롬프트에는 최소한 아래 세 덩어리가 같이 들어가야 한다.

- 현재 게임 상태
- 최근 전략 피드백 요약
- 캐릭터의 장기 기억 요약

### 10.8 In-Context RL에서 필요한 기록 항목

학습용 숫자 체크포인트 대신 아래 로그가 중요하다.

- 현재 손패와 공개 상태
- 선택 행동
- 행동 이유
- 실제 결과
- 쇼다운 결과
- 해당 행동에 대한 사후 피드백
- 다음 턴 프롬프트에 반영된 요약

즉, 핵심 산출물은 `모델 체크포인트`가 아니라 `좋은 텍스트 피드백 체인`이다.

### 10.9 이 프로젝트에서 정책 개선의 실체

이 프로젝트에서 정책 개선은 다음 셋의 결합이다.

- 행동 결과에 대한 텍스트 평가
- 메모리 누적
- 다음 프롬프트에서의 자기 수정

정리하면:

- 전략 개선 메커니즘: in-context reinforcement learning
- 전략 저장 매체: memory
- 캐릭터 표현: LLM
- 최종 합법성 검증: 포커 엔진

이게 지금 프로젝트 목표에 가장 맞는 구조다.

## 13. 캐릭터 레이어

이 프로젝트가 재미있어지려면 상대는 단순한 포커 봇이 아니라 캐릭터여야 한다.

각 캐릭터는 최소한 아래 정보를 가져야 한다.

- 이름
- 말투
- 표정 세트
- 포커 스타일
- 블러프 성향
- 위험 선호도
- 플레이어와의 관계 변수

예시 캐릭터 타입:

- 공격적인 블러퍼
- 보수적인 계산형
- 장난기 많은 트릭스터
- 심리전을 거는 로맨스형
- 냉정한 확률 계산형

이 성격 정보는 두 군데에 영향을 줘야 한다.

- 포커 행동 선택
- 행동 직후 출력되는 대사

## 14. 모드 전환

### 13.1 Human vs LLM

가장 먼저 완성해야 할 모드다.

- 구현 범위가 가장 작다.
- 데모 시연이 쉽다.
- LLM 의사결정 품질을 보여주기 좋다.

### 13.2 LLM vs Scripted NPC

비교 기준을 만들 때 좋다.

- LLM과 규칙 기반 AI 비교 가능
- 테스트 자동화에 유리

### 13.3 LLM vs LLM

연구/실험 느낌을 주는 모드다.

- 자동 대전 가능
- 로그 수집 가능
- 플레이 스타일 비교 가능

## 15. 기록하면 좋은 통계

- 총 플레이 핸드 수
- 승률
- 쇼다운 승률
- 폴드 비율
- 콜 비율
- 레이즈 비율
- 평균 팟 크기
- 평균 교체 카드 수
- 블러프 추정 비율
- LLM 응답 오류 횟수

## 16. 구현 로드맵

### 1단계: 포커 코어 정리

목표:

- 2인용 5 Card Draw 엔진 완성

필수 산출물:

- 정확한 족보 판정
- 타이브레이커
- 베팅 상태 모델
- 쇼다운 처리

### 2단계: Ren'Py UI 연결

목표:

- 사람이 실제로 한 판을 진행 가능하게 만들기

필수 산출물:

- 카드 선택 UI
- 베팅 버튼 UI
- 결과창
- 칩/팟 표시

### 3단계: LLM 에이전트 연결

목표:

- 상대 한 자리를 LLM으로 구동

필수 산출물:

- 프롬프트 생성기
- JSON 응답 파서
- 실패 시 폴백 로직
- 액션 로그

### 4단계: 데모 품질 개선

목표:

- 배포 가능한 수준으로 마감

필수 산출물:

- 통계 화면
- 자동 대전 모드
- 모델 설정 화면
- 밸런스 조정

## 17. 기술 리스크

### 15.1 LLM 응답 불안정

문제:

- JSON이 깨질 수 있다.
- 불법 행동을 낼 수 있다.

대응:

- 엄격한 스키마 검증
- 합법 행동 목록 제공
- 실패 시 안전 행동 사용

### 15.2 비용과 지연

문제:

- 행동마다 API 호출이 들어가면 느릴 수 있다.

대응:

- 작은 모델을 우선 사용
- 프롬프트를 짧게 유지
- 시스템 프롬프트 재사용
- 필요 시 로컬 모델 옵션 추가

### 15.3 게임 로직 오류

문제:

- 승패 판정이 틀리면 프로젝트 신뢰도가 바로 무너진다.

대응:

- 족보 비교 로직 분리
- 테스트 가능한 순수 함수화
- UI와 엔진 분리

### 15.4 정보 누출

문제:

- LLM이 상대 손패를 보면 게임이 무너진다.

대응:

- 좌석별 상태 뷰를 별도로 생성
- 공개 정보와 비공개 정보를 엄격히 분리

## 18. 첫 번째 LLM 계약안

실제 구현 시작용으로는 아래 정도가 적당하다.

시스템 프롬프트:

```text
당신은 5 Card Draw 포커 게임의 AI 상대입니다.
항상 합법적인 행동만 선택하세요.
제공되지 않은 숨겨진 정보는 추론하되 사실처럼 단정하지 마세요.
반드시 JSON만 출력하세요.
```

입력 예시:

```json
{
  "phase": "betting_round_1",
  "persona": {
    "name": "Reina",
    "style": "도발적이고 침착하며 중간 정도로 공격적"
  },
  "private_hand": [
    "KS",
    "QS",
    "QD",
    "7C",
    "2H"
  ],
  "public_state": {
    "pot": 50,
    "your_stack": 190,
    "opponent_stack": 210,
    "to_call": 10,
    "legal_actions": [
      {"action": "fold"},
      {"action": "call"},
      {"action": "raise", "amount": 20},
      {"action": "raise", "amount": 40}
    ]
  }
}
```

출력 예시:

```json
{
  "action": "raise",
  "amount": 20,
  "reason": "퀸 페어와 선공 압박을 동시에 활용하기 위해 작은 레이즈를 선택한다."
}
```

## 19. 현재 기준 완료 조건

현재 기준으로 아래 조건을 만족하면 문서와 구현이 일치한다고 본다.

- 사람이 2인 포커 매치를 끝까지 플레이할 수 있다.
- 상대는 `LLM NPC`와 `스크립트봇` 사이를 옵션에서 전환할 수 있다.
- 모든 행동은 엔진이 검증한다.
- 쇼다운 승패 판정과 타이브레이커가 정확하다.
- LLM NPC는 플레이어 손패를 보지 않고 공개 정보만 사용한다.
- LLM NPC는 베팅, 카드 교체, 대사를 모두 문맥 기반으로 생성할 수 있다.
- 결과 피드백과 기억이 다음 행동 정책과 대사 정책에 반영된다.
- 저장, 불러오기, 로그 보기, 환경 설정, 메인 메뉴 이동이 화면에서 접근 가능하다.
