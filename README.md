![LLMoker 배너](docs/seam_interp_prev_00001.gif)

# LLMoker

Ren'Py 기반 5드로우 포커 게임에 로컬 LLM NPC, 심리전 대사, ICRL 스타일 정책 업데이트를 결합한 프로젝트입니다.

## 현재 구현 상태

- 2인 5드로우 포커 규칙 구현
- 앤티 고정, 2회 베팅, 드로우, 쇼다운 흐름 구현
- `스크립트봇`과 `LLM NPC` 상대 지원
- LLM 행동 선택, 카드 교체 판단, 대사 생성 연결
- 공개 정보와 비공개 정보 분리
- 메모리, 리플레이, 세이브를 SQLite로 관리
- 메인 메뉴와 포커 화면에 `webm` 영상 배경 적용
- 게임 UI는 한국어 기준으로 정리
- LLM 디버그용 터미널 로그 출력

## 영상 자산

- 메인 메뉴: `llmoker/game/gui/main.webm`
- 포커 기본 배경: `llmoker/game/images/minigames/normal.webm`
- 라운드 종료 시 플레이어 승리: `llmoker/game/images/minigames/lost.webm`
- 라운드 종료 시 NPC 승리: `llmoker/game/images/minigames/win.webm`

## LLM NPC 요약

- 기본 상대 AI는 `LLM NPC`
- 로컬 모델은 `llmoker/models/llm/` 아래를 사용
- 현재 기본 모델 경로는 `backend/config.py`에서 결정
- LLM 워커는 `llmoker/.venv/bin/python`으로 별도 실행
- `vLLM + bitsandbytes 4비트`와 `Transformers` 백엔드를 지원
- 현재 구현은 `vLLM` 실패 시 자동 폴백하지 않고, 실패 원인을 그대로 표시

중요:

- `vLLM 4비트`는 CUDA GPU가 실제로 보이는 환경에서만 동작합니다.
- 현재 WSL/OS가 GPU를 노출하지 않으면 `Transformers`를 직접 선택해야 합니다.

## 디버그 로그

게임 UI에서는 NPC 손패와 비공개 정보를 숨기지만, 터미널에는 아래 로그를 출력합니다.

- 라운드 시작 시 NPC 손패와 족보
- 베팅 시 허용 행동, 선택 행동, 이유
- 드로우 전후 손패와 교체 인덱스
- 쇼다운/폴드 종료 결과
- 대사 생성 결과

로그 형식:

```text
[LLMoker][DEBUG] ...
```

## 실행

프로젝트 루트:

```bash
cd /home/hosung/pytorch-demo/LLMoker
```

게임 실행:

```bash
cd llmoker
./5Drawminigame.sh
```

개발용 자동 매치 테스트:

```bash
cd llmoker
python3 scripts/run_match.py
```

## 문서

- [블루프린트](docs/blueprint.md)
- [LLM NPC 설정](docs/llm_npc_setup.md)
- [대사 시스템](docs/dialogue_system.md)
- [ICRL 정책 업데이트](docs/icrl_policy_update.md)
- [Ren'Py 런타임 구조](docs/renpy_engine.md)

## 핵심 파일

- `llmoker/backend/poker_engine.py`
- `llmoker/backend/llm_agent.py`
- `llmoker/backend/prompt_builder.py`
- `llmoker/scripts/llm_runtime_worker.py`
- `llmoker/scripts/run_match.py`
- `llmoker/game/poker_minigame.rpy`
- `llmoker/game/poker_ui.rpy`
- `llmoker/game/poker_dialogue.rpy`

## 현재 주의사항

- `vLLM 4비트`는 코드만으로 해결되지 않고 GPU 런타임 접근이 필요합니다.
- Ren'Py UI에 백엔드 예외 문자열을 올릴 때는 `{}` 같은 태그 문자를 이스케이프해야 합니다.
- SQLite는 Ren'Py 본체가 직접 사용하므로 `.venv`가 아니라 `vendor/` 경로를 사용합니다.
