default poker_status_text = ""
default poker_round_summary_text = ""
default poker_match_intro_seen = False

init python:
    def _escape_renpy_say_text(text):
        """
        Ren'Py say에서 해석되는 치환 문자들을 일반 문자열로 바꾼다.

        Args:
            text: 대사창에 넣을 원문 문자열이다.

        Returns:
            Ren'Py 치환 문자가 이스케이프된 문자열이다.
        """

        if text is None:
            return ""

        escaped = str(text)
        escaped = escaped.replace("%", "%%")
        escaped = escaped.replace("[", "[[")
        escaped = escaped.replace("{", "{{")
        escaped = escaped.replace("}", "}}")
        return escaped

    def update_status_from_messages(messages, fallback=None):
        """
        최근 처리 결과 로그에서 마지막 문장만 뽑아 상태 표시줄에 반영한다.
        새 로그가 없을 때만 `fallback`을 써서, 예전 상태 문구가 불필요하게 덮어써지지 않게 한다.

        Args:
            messages: 최근 처리 결과 로그 목록이다.
            fallback: 로그가 비었을 때 대신 넣을 문자열이다.
        """

        if messages:
            store.poker_status_text = messages[-1]
        elif fallback is not None:
            store.poker_status_text = fallback

    def _dialogue_event_lines(event_name, messages=None):
        """
        현재 상황에 맞는 스크립트 대사 목록을 생성한다.

        Args:
            event_name: 대사 이벤트 이름이다.
            messages: 직전 처리 결과 로그 목록이다.

        Returns:
            `(speaker_key, text)` 튜플 목록이다.
        """

        match = get_poker_match()
        lines = []
        messages = messages or []

        if event_name == "match_intro":
            lines.append(("sb", "좋아. 말보다 패로 보여줘. 오늘은 쉽게 안 끝날 거야."))
            lines.append(("sb", "앤티는 이미 테이블에 올라갔어. 시작하지."))
            return lines

        if event_name == "round_start":
            if match.hand_no == 1:
                return [("sb", "첫 판이야. 네 패를 끝까지 믿을 수 있을지 보자.")]
            if match.hand_no % 3 == 0:
                return [("sb", "세 번째, 여섯 번째 판쯤 되면 습관이 보이기 시작하지.")]
            return [("sb", "새 라운드다. 이번엔 어떤 표정으로 칩을 밀어 넣을래?")]

        if event_name == "betting":
            joined = " ".join(messages)
            if "레이즈" in joined:
                return [("sb", "좋아, 판이 좀 커지는군. 그 정도 압박은 반갑지.")]
            if "베팅했습니다" in joined and "당신" in joined:
                return [("sb", "먼저 건다고 강한 패라는 뜻은 아니지. 그래도 받아줄게.")]
            if "스크립트봇이(가) 10칩 베팅했습니다." in joined:
                return [("sb", "망설일 필요 없어. 받을지 버릴지 지금 정해.")]
            if "당신이(가) 체크했습니다." in joined:
                return [("sb", "신중한 척은 좋은데, 그게 약함을 숨겨주진 않아.")]
            if "폴드" in joined:
                return [("sb", "이번 판은 여기까지네. 다음엔 더 오래 버텨 봐.")]
            if "콜" in joined:
                return [("sb", "좋아, 계속 보자는 거네. 그 선택 기억해 둘게.")]
            return []

        if event_name == "draw":
            player_discards = len(store.poker_selected_discards)
            if player_discards == 0:
                return [("sb", "패를 그대로 간다? 그 자신감, 허세만 아니면 좋겠네.")]
            if player_discards >= 3:
                return [("sb", "세 장 이상 갈아치우는군. 꽤 과감한데.")]
            return [("sb", "필요한 카드만 고르는 건 좋지. 문제는 네가 맞췄느냐는 거야.")]

        if event_name == "round_end":
            if not match.round_summary:
                return []
            winner = match.round_summary["winner"]
            if winner == match.player.name:
                return [
                    ("sb", "좋은 판정이었어. 이번 라운드는 네가 가져가도 할 말 없네."),
                    ("sys", "라운드 승리. 다음 라운드를 준비할 수 있습니다." if match.can_continue_match() else "라운드 승리. 상대 스택이 부족해 매치가 종료됩니다."),
                ]
            if winner == match.bot.name:
                return [
                    ("sb", "봐, 결국 팟은 내 쪽으로 왔어. 압박을 견디지 못했네."),
                    ("sys", "라운드 패배. 다음 라운드를 준비할 수 있습니다." if match.can_continue_match() else "라운드 패배. 당신 스택이 부족해 매치가 종료됩니다."),
                ]
            return [
                ("sb", "무승부라. 서로 완전히 읽어내진 못했다는 뜻이겠지."),
                ("sys", "무승부입니다. 팟이 분배되었습니다."),
            ]

        if event_name == "match_end":
            if match.player.stack > match.bot.stack:
                return [("sb", "오늘 매치는 네가 가져갔네. 다음엔 같은 흐름을 기대하지 마.")]
            if match.player.stack < match.bot.stack:
                return [("sb", "칩은 전부 흐름을 기억해. 오늘은 내가 더 정확했어.")]
            return [("sb", "끝까지 가도 동수라니. 다음엔 확실히 결판 내자.")]

        return lines

    def _round_result_summary_text(match):
        """
        라운드 결과를 대사 프롬프트용 요약으로 변환한다.

        Args:
            match: 현재 포커 매치 객체다.

        Returns:
            대사 프롬프트에 넣을 라운드 요약 문자열 또는 None이다.
        """

        if not match.round_summary:
            return None

        summary = match.round_summary
        return "승자: %s / 플레이어 족보: %s / 상대 족보: %s / 팟: %d칩" % (
            summary["winner"],
            summary["player_hand_name"],
            summary["bot_hand_name"],
            summary["pot"],
        )

    def _llm_dialogue_lines(event_name, messages=None):
        """
        LLM NPC가 생성한 대사를 화면용 튜플 목록으로 만든다.

        Args:
            event_name: 대사 이벤트 이름이다.
            messages: 직전 처리 결과 로그 목록이다.

        Returns:
            `(speaker_key, text)` 튜플 목록이다.
        """

        match = get_poker_match()
        if match.bot_mode != "llm_npc":
            return []

        result_summary = _round_result_summary_text(match)
        generation = match.llm_agent.generate_dialogue(match, event_name, result_summary=result_summary)
        if generation.get("status") != "ok":
            reason = (generation.get("reason") or "").strip() or "LLM 대사 생성 실패"
            match._debug_terminal_log("%s 대사 생성 실패 / 이벤트: %s / 이유: %s" % (
                match.bot.name,
                event_name,
                reason,
            ))
            return [("sys", "LLM NPC 대사 생성 실패: %s" % reason)]
        dialogue_text = generation.get("text", "").strip()
        if not dialogue_text:
            return []

        lines = []
        for text in [line.strip() for line in dialogue_text.splitlines() if line.strip()]:
            lines.append(("sb", text))

        if lines:
            log_line = "[LLM NPC] %s 대사 생성: %s" % (match.bot.name, " / ".join(text for _, text in lines))
            match.action_log.append(log_line)
            store.poker_status_text = log_line
            match._debug_terminal_log("%s 대사 생성 / 이벤트: %s / 내용: %s" % (
                match.bot.name,
                event_name,
                " / ".join(text for _, text in lines),
            ))
        return lines

    def play_dialogue_event(event_name, messages=None):
        """
        현재 이벤트에 맞는 대사를 만들고, 전용 배경 화면 위에서 순서대로 출력한다.
        LLM NPC 모드면 LLM 대사를 먼저 시도하고, 아니라면 스크립트 대사 테이블을 사용한다.

        Args:
            event_name: 대사 이벤트 이름이다.
            messages: 직전 처리 결과 로그 목록이다.
        """

        lines = _llm_dialogue_lines(event_name, messages)
        if not lines and get_poker_match().bot_mode != "llm_npc":
            lines = _dialogue_event_lines(event_name, messages)

        renpy.show_screen(
            "poker_dialogue_backdrop",
            video_name=get_poker_dialogue_background_name(event_name),
        )

        speaker_map = {
            "sb": store.sb,
            "sys": store.sys,
            "narrator": None,
        }

        for speaker_key, text in lines:
            speaker = speaker_map.get(speaker_key)
            safe_text = _escape_renpy_say_text(text)
            if speaker is None:
                renpy.say(None, safe_text)
            else:
                renpy.say(speaker, safe_text)

        renpy.hide_screen("poker_dialogue_backdrop")
