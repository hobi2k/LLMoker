# LLMoker 작업 규칙

## 필수 선행 작업

**모든 작업 전에 반드시 아래를 먼저 읽는다.**

1. `docs/blueprint.md` — 프로젝트 전체 구조와 설계 원칙
2. `docs/styleguide.md` — 코드 작성, 독스트링, 주석, 네이밍, QA 문서 기준
3. 작업 대상 파일과 관련된 `cookbook/` 문서 — 파일별 역할, 감사 포인트, 증상별 추적 경로

관련 cookbook 매핑:

| 작업 대상 | 먼저 읽을 문서 |
|---|---|
| 포커 엔진 (`poker_engine.py`) | `cookbook/02_poker_engine.md` |
| LLM 백엔드 (`agent.py`, `client.py`, `runtime.py`, `tasks.py`, `prompts.py`) | `cookbook/03_llm_backend.md` |
| 기억, 회고, 세이브 | `cookbook/04_memory_and_save.md` |
| Ren'Py UI (`*.rpy`) | `cookbook/05_renpy_ui.md` |
| 오류 추적 | `cookbook/06_symptom_audit.md` |
| 특정 파일 함수 | `cookbook/07_file_reference.md` |

## 코드 수정 후 필수 작업

코드를 수정하면 반드시 관련 `docs/`와 `cookbook/` 문서도 함께 업데이트한다.

업데이트 대상 판단 기준:

- 함수 동작이 바뀌었으면 `cookbook/03_llm_backend.md` 또는 `cookbook/07_file_reference.md` 해당 항목 갱신
- 새 버그 패턴이나 증상이 발견됐으면 `cookbook/06_symptom_audit.md` 갱신
- 설계 원칙이나 구조가 바뀌었으면 `docs/` 관련 문서 갱신

## 코드 작성 시 준수 사항 (styleguide.md 핵심)

- 함수와 클래스는 반드시 한국어 독스트링을 작성한다 (`Args:` / `Returns:` 포함).
- 독스트링 첫 줄은 "무슨 일을 하는지"를 자연스러운 문장으로 적는다. 자동 생성 냄새 문구 금지.
- UI(`*.rpy`), 게임 규칙(`poker_engine.py`), LLM 연결(`llm/`), 저장 로직은 섞지 않는다.
- `renpy.say()`에 들어가는 문자열에서 `{`, `}`, `[`, `%` 충돌을 반드시 이스케이프한다.
- 코드만 봐도 분명한 줄에는 주석을 달지 않는다.

## QA 기준 (styleguide.md 핵심)

- QA 문서: `docs/qa_YYYYMMDD.md`
- QA 결과 문서: `docs/qa_reqult_YYYYMMDD.md`
- 자동 검증(문법·lint·import)과 수동 GUI QA(연출·대사·지연)는 분리해서 기록한다.

## 절대 하지 않는 것

- docs/cookbook/styleguide를 읽지 않고 코드를 수정하지 않는다.
- 문서에 없는 설계 결정을 임의로 내리지 않는다. 확실하지 않으면 먼저 묻는다.
- 로컬 모델 폴더 내부 파일을 수정하지 않는다.
