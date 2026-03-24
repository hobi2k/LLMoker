# 01. 게임 한 판의 흐름

[목차로 돌아가기](README.md)

이 장은 **LLMoker 한 판이 실제로 어떤 순서로 시작되고 끝나는지** 설명한다.  
파일 이름보다 `시간 순서`와 `상태 변화`를 중심으로 읽는 장이다.

## 1. 시작점

게임 실행의 제일 바깥쪽은 `llmoker/5Drawminigame.sh`다.

이 스크립트의 책임:

- 모델 bootstrap 실행
- 외부 Python 3.11 LLM 런타임 준비
- Ren'Py 실행
- 종료 시 LLM 런타임 정리

이 단계에서 보면 되는 문제:

- 게임 시작이 유난히 오래 걸리는가
- 종료 후 런타임 프로세스가 남는가
- 모델 경로 안내와 실제 경로가 다른가

이 단계에서 하면 안 되는 일:

- 포커 룰 계산
- 프롬프트 생성
- 세이브 상태 조작

## 2. Ren'Py 진입

프로그램 시작 직후 가장 먼저 보는 진입점은 `llmoker/game/script.rpy`의 `label splashscreen`이다.

이 라벨이 하는 일:

1. `gui/logo.webm` 재생
2. 안내 문구를 짧게 띄운다
3. `gui/intro_with_audio.webm` 재생
4. 짧은 검은 화면 전환
5. `gui/openingcinema.webm` 재생
6. 메인 메뉴 배경으로 디졸브 전환한다
7. 이 구간에서 `begin_llm_npc_prewarm()`이 백그라운드로 돌아간다
8. `label start`는 이미 준비된 런타임을 이어받는다

그 다음 `label start`가 하는 일:

1. 백그라운드 예열 결과를 확인한다
2. 아직 덜 올라온 경우 남은 초기화를 마무리한다
3. `poker_minigame`으로 이동한다

실제 미니게임 흐름은 그 다음 `llmoker/game/poker_minigame.rpy`의 `label poker_minigame`에서 이어진다.

이 라벨이 하는 일:

1. 배경 음악 재생
2. `match_intro` 대사 실행
3. 새 라운드 시작
4. `round_start` 대사 실행
5. 상태 문구 초기화
6. `poker_phase_loop`로 이동

여기서 중요한 점:

- 이 파일은 게임의 **흐름**을 잡는다.
- 게임의 **규칙**을 계산하지는 않는다.
- 인트로 영상/오프닝 시퀀스와 런타임 예열은 `script.rpy`에서 먼저 처리하고 들어온다.
- `poker_minigame.rpy`는 이미 준비된 상태를 재사용한다.

즉 라벨 파일이 직접 합법 행동을 고르거나 승패를 계산하면 구조가 바로 무너진다.

## 3. 라운드 루프

라운드 중 핵심 라벨은 `label poker_phase_loop`다.

이 라벨은 현재 `PokerMatch.phase`를 보고 아래 셋 중 하나로 분기한다.

- `betting1` 또는 `betting2`
- `draw`
- `round_end`

### 3.1 베팅 페이즈

베팅 페이즈에서 일어나는 일:

1. 상태 텍스트를 `get_betting_status_text()`로 갱신
2. `screen poker_table_screen(mode="betting")` 호출
3. 플레이어 입력 수집
4. `safe_resolve_player_action(action)` 호출
5. 결과 로그로 상태 텍스트 갱신
6. `play_dialogue_event("betting", round_messages)` 호출

핵심 포인트:

- 플레이어 행동 적용은 엔진에서 일어난다.
- 대사는 베팅 처리 뒤에 붙는다.
- 플레이어 로그가 빈약하면 봇만 연속으로 움직이는 것처럼 보일 수 있다.

### 3.2 드로우 페이즈

드로우 페이즈에서 일어나는 일:

1. 드로우 안내 문구 표시
2. `screen poker_table_screen(mode="draw")` 호출
3. `play_dialogue_event("draw")`
4. `safe_resolve_draw_phase(selected_discards)` 호출
5. 선택 상태 초기화
6. 결과 메시지로 상태 텍스트 갱신

핵심 포인트:

- 드로우 페이즈는 플레이어 입력과 봇 카드 교체가 함께 처리된다.
- 내부 카드 교체 이유가 `public_log`로 새면 이후 대사와 판단 품질이 함께 무너진다.

### 3.3 라운드 종료

종료 시 흐름:

1. `poker_round_summary_text` 구성
2. `screen poker_table_screen(mode="round_end")`를 먼저 띄운다
3. `play_dialogue_event("round_end")`
4. 매치 종료면 `play_dialogue_event("match_end")`
5. 결과 화면을 다시 입력형 screen으로 열어 다음 라운드 또는 메인 메뉴를 고른다

결과 화면은 이 시점의 스냅샷을 먼저 보여주고, 그 위에서 종료 대사가 이어진다.  
승패 판정 자체는 이미 엔진이 끝냈다.

## 4. Ren'Py에서 백엔드로 넘어가는 접착층

`llmoker/game/poker_core.rpy`가 Ren'Py와 백엔드를 연결한다.

중심 함수는 `ensure_poker_runtime()`다.

이 함수의 역할:

- `MemoryManager` 준비
- `ReplayLogger` 준비
- `SaveStateStore` 준비
- `PokerMatch` 생성 또는 복원
- 현재 설정을 런타임에 재적용

새 게임 경로:

- 세이브 스냅샷이 없으면 기억을 비우고 새 `PokerMatch`를 만든다.

복원 경로:

- `store.poker_match_state`가 있으면 `PokerMatch.from_snapshot()`으로 복원한다.

이 함수가 잘못되면 생기는 문제:

- 새 게임인데 기억이 남는다
- 세이브를 불렀는데 기억이 안 돌아온다
- 설정은 바뀌었는데 런타임에 반영되지 않는다

## 5. 실제 상태 변화는 어디서 일어나는가

게임 상태를 실제로 바꾸는 함수는 세 개가 핵심이다.

- `PokerMatch.start_new_round()`
- `PokerMatch.resolve_player_action()`
- `PokerMatch.resolve_draw_phase()`

이 셋이 포커 판의 진짜 흐름을 만든다.

따라서 “화면이 이상하다”, “LLM이 이상하다” 같은 문제가 보여도,  
먼저 이 셋에서 상태가 올바르게 바뀌는지 확인해야 한다.

## 6. 이 장을 읽고 나서 확인할 것

다음 장으로 넘어가기 전에 아래 질문에 답할 수 있어야 한다.

- 시작 대사와 라운드 시작 대사는 어디서 호출되는가
- 플레이어 입력은 어느 screen에서 받고, 어느 함수가 상태를 바꾸는가
- 드로우는 플레이어와 봇 처리를 어디서 함께 하는가
- 새 게임과 저장 복원은 어느 함수에서 갈리는가

다음 장: [02. 포커 엔진](02_poker_engine.md)
