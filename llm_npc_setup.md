# LLM NPC 설정 문서

## 1. 목적

이 문서는 `LLMoker/llmoker/models/llm/saya_rp_4b_v3`를 기준으로 LLM NPC를 어떻게 연결하는지 정리한다.

## 2. 현재 연결 방식

현재 구조는 아래와 같다.

1. Ren'Py 게임은 `backend/poker_engine.py`에서 현재 상대 AI 모드를 확인한다.
2. 상대 AI 모드가 `llm_npc`이면 `backend/llm_agent.py`를 사용한다.
3. `LocalLLMAgent`는 `scripts/llm_runtime_worker.py`를 `python3` 서브프로세스로 실행한다.
4. 워커가 모델을 한 번 로드한 뒤 JSON 라인 방식으로 행동 요청을 처리한다.
5. 실패하면 합법 행동 중 안전한 폴백으로 떨어진다.

## 3. 현재 모델 경로

- 기본 모델 경로: `llmoker/models/llm/saya_rp_4b_v3`

현재 `config.py`는 이 폴더가 있으면 기본 LLM 경로로 우선 사용한다.

## 4. 왜 서브프로세스 워커를 쓰는가

Ren'Py 번들 Python과 실제 로컬 추론 환경은 분리하는 편이 안전하다.

이 구조를 쓰는 이유:

- Ren'Py 런타임에 `torch`, `transformers`가 없을 수 있다.
- 게임 UI 프로세스와 모델 추론 프로세스를 분리할 수 있다.
- 모델은 워커에서 한 번만 로드하고 재사용할 수 있다.

## 5. 현재 필요한 Python 의존성

LLM NPC를 실제 추론까지 쓰려면 `python3` 환경에 아래 패키지가 필요하다.

- `torch`
- `transformers`
- `accelerate`

현재 이 작업 환경에서는 위 패키지가 없어, `LLM NPC` 모드로 바꿔도 안전 폴백이 동작한다.

즉:

- UI 전환은 구현됨
- 모델 경로 연결도 구현됨
- 워커 구조도 구현됨
- 실제 추론은 시스템 Python 의존성 설치 후 활성화됨

## 6. 게임 내 옵션 위치

게임 하단의 `환경 설정` 버튼에서 상대 AI를 바꿀 수 있다.

- `스크립트봇 사용`
- `LLM NPC 사용`

같은 화면에서 아래 정보도 확인할 수 있다.

- 현재 상대 AI 모드
- 현재 모델 경로
- 현재 LLM 상태

## 7. 관련 파일

- [config.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/config.py)
- [llm_agent.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/llm_agent.py)
- [prompt_builder.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/prompt_builder.py)
- [poker_engine.py](/home/hosung/pytorch-demo/LLMoker/llmoker/backend/poker_engine.py)
- [llm_runtime_worker.py](/home/hosung/pytorch-demo/LLMoker/llmoker/scripts/llm_runtime_worker.py)
- [poker_ui.rpy](/home/hosung/pytorch-demo/LLMoker/llmoker/game/poker_ui.rpy)

## 8. 다음 단계

실제 LLM NPC 품질을 올리려면 다음 순서가 맞다.

1. `python3` 환경에 추론 의존성 설치
2. 워커에서 GPU/CPU 조건별 로딩 옵션 조정
3. 대사 생성과 행동 생성을 분리
4. memory와 recent feedback를 프롬프트에 더 정교하게 반영
5. LLM 실패 시 현재처럼 안전 폴백 유지
