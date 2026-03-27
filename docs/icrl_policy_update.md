# ICRL 기반 행동 정책 업데이트 문서

## 1. 목적

이 문서는 `LLMoker`에서 말하는 강화학습이 무엇인지 분명하게 정리한다.

이 프로젝트에서 말하는 핵심은 파인튜닝이 아니다.  
로컬 모델의 가중치를 직접 업데이트하지 않고, 라운드 회고를 다음 추론 문맥에 다시 넣어 행동 정책을 수정하는 방식이다.

## 2. 참고 논문

- arXiv: [In-Context Reinforcement Learning for Tool Use in Large Language Models](https://arxiv.org/abs/2603.08068)

위 논문은 `SFT + RL` 파이프라인 대신, 롤아웃 프롬프트 안에 예시와 피드백을 넣어 정책을 문맥 내에서 학습시키는 `ICRL` 관점을 제시한다.

이 프로젝트는 논문의 문제 설정과 완전히 같지는 않다.  
다만 아래 핵심 아이디어를 포커 NPC에 맞게 가져온다.

- 가중치 업데이트 없이 정책을 수정한다.
- 이전 결과를 다음 추론 문맥에 다시 넣는다.
- 문맥 속 경험이 다음 행동 선택에 영향을 준다.

## 3. LLMoker에서의 해석

`LLMoker`에서 `ICRL`은 아래 의미로 사용한다.

- 모델 파라미터를 학습하지 않는다.
- 별도 파인튜닝 체크포인트를 만들지 않는다.
- 라운드 결과를 LLM 회고 텍스트로 만든다.
- 그 피드백을 메모리에 저장한다.
- 다음 행동 프롬프트와 카드 교체 프롬프트에 다시 넣는다.

즉, 이 프로젝트에서 정책 업데이트는:

`라운드 결과 -> 텍스트 피드백 -> 메모리 저장 -> 다음 프롬프트 반영 -> 다음 행동 정책 변화`

로 이해해야 한다.

## 4. 포커 게임에 맞춘 정책 업데이트 흐름

현재 구조는 아래 순서로 움직인다.

1. 라운드가 끝난다.
2. `policy_loop.py`가 결과를 읽는다.
3. 승패, 폴드 여부, 족보 비교를 바탕으로 확정 사실을 정리한다.
4. 현재 `LLM NPC` 모드에서는 `policy_loop.py`가 이 확정 사실과 공개 로그를 다시 LLM에 보내 정책 회고를 만든다.
5. 이 요청은 `Qwen-Agent` tool calling 형식으로 `get_round_summary`, `get_recent_log`, `get_memory`를 조회하면서 수행한다.
6. `memory_manager.py`가 이를 SQLite 메모리에 저장한다.
7. 다음 라운드에서 `backend/llm/agent.py`가 같은 도구 경로로 최근 피드백과 장기 기억을 다시 조회하게 한다.
8. 그 문맥을 바탕으로 다음 행동 정책을 고른다.

즉, 학습의 대상은 모델 가중치가 아니라 `현재 추론 문맥 안의 정책`이다.

## 5. 플레이어 비공개 정보 제약

정책 업데이트가 들어가도 정보 경계는 무너지면 안 된다.

LLM NPC가 볼 수 있는 정보:

- 자기 손패
- 팟
- 양측 스택
- 현재 콜 금액
- 공개 행동 로그
  - 체크
  - 베팅
  - 콜
  - 레이즈
  - 폴드
  - 카드 교체 여부와 장수
- 라운드 결과

LLM NPC가 보면 안 되는 정보:

- 플레이어 실제 손패
- 드로우 이후 플레이어 카드 구성
- 비공개 내부 상태

그래서 엔진은 `action_log`와 `public_log`를 분리한다.

- `action_log`
  - 내부 디버그와 플레이어 개인 정보까지 포함될 수 있다.
- `public_log`
  - NPC가 참고 가능한 공개 정보만 들어간다.

ICRL도 반드시 `public_log` 기준으로만 적용한다.

## 6. 행동 정책 업데이트와 카드 교체 업데이트

이 프로젝트에서 정책 업데이트 대상은 행동만이 아니다.

- 행동 정책
  - 체크
  - 베팅
  - 콜
  - 레이즈
  - 폴드
- 정책 회고
  - 직전 라운드에서 무엇이 먹혔는지
  - 다음 라운드에서 무엇을 우선 볼지
- 드로우 정책
  - 어떤 카드를 몇 장 교체할지

즉, 같은 기억과 피드백을 바탕으로:

- 포커 행동도 바뀌고
- 카드 교체 판단도 바뀐다.

## 7. 현재 구현 상태

현재 실제 연결 상태는 아래와 같다.

- 행동 선택 ICRL 경로: 연결됨
- 정책 피드백 ICRL 경로: 연결됨
- 카드 교체 ICRL 경로: 연결됨
- 모델 파라미터 학습: 없음
- 파인튜닝: 없음
- 검증 보조용 터미널 디버그 로그: 연결됨

즉, 현재 `LLMoker`의 강화학습 해석은:

`문맥 내 정책 업데이트`

이며, 이 점을 문서와 코드에서 계속 일관되게 유지해야 한다.

## 8. 구현 파일

- [policy_loop.py](llmoker/backend/policy_loop.py)
- [memory_manager.py](llmoker/backend/memory_manager.py)
- [prompts.py](llmoker/backend/llm/prompts.py)
- [agent.py](llmoker/backend/llm/agent.py)
- [tools.py](llmoker/backend/llm/tools.py)
- [poker_engine.py](llmoker/backend/poker_engine.py)
- [poker_dialogue.rpy](llmoker/game/poker_dialogue.rpy)
