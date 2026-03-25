default poker_status_text = ""
default poker_round_summary_text = ""
default poker_match_intro_seen = False

init python:
    import re

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

    def _action_summary_lines(messages=None):
        """
        엔진 로그 문장을 화면에 보여줄 짧은 행동 요약으로 바꾼다.

        Args:
            messages: 최근 처리 결과 로그 목록이다.

        Returns:
            `(speaker_key, text)` 튜플 목록이다.
        """

        lines = []
        for raw in messages or []:
            text = " ".join(str(raw or "").split())
            if not text:
                continue
            if text.startswith("당신의 현재 손패:"):
                continue
            def display_actor(actor_text):
                actor_text = (actor_text or "").strip()
                if actor_text == "당신":
                    return "플레이어"
                return actor_text
            if text == "드로우 단계로 넘어갑니다.":
                lines.append(("sys", "첫 번째 베팅이 끝나고 드로우 단계가 시작됐다."))
                continue
            if "이(가) 체크했습니다." in text:
                actor = display_actor(text.split("이(가) 체크했습니다.", 1)[0])
                lines.append(("sys", "%s는 체크했다." % actor))
                continue
            if "이(가) 폴드했습니다." in text:
                actor = display_actor(text.split("이(가) 폴드했습니다.", 1)[0])
                lines.append(("sys", "%s는 폴드했다." % actor))
                continue
            bet_match = re.match(r"(.+?)이\(가\) (\d+)칩 베팅했습니다\.", text)
            if bet_match:
                lines.append(("sys", "%s는 %s칩 베팅했다." % (display_actor(bet_match.group(1)), bet_match.group(2))))
                continue
            call_match = re.match(r"(.+?)이\(가\) (\d+)칩 콜했습니다\.", text)
            if call_match:
                lines.append(("sys", "%s는 %s칩 콜했다." % (display_actor(call_match.group(1)), call_match.group(2))))
                continue
            raise_match = re.match(r"(.+?)이\(가\) (\d+)칩을 더 올려 총 (\d+)칩이 되도록 레이즈했습니다\.", text)
            if raise_match:
                lines.append(("sys", "%s는 총 %s칩까지 레이즈했다." % (display_actor(raise_match.group(1)), raise_match.group(3))))
                continue
            draw_match = re.match(r"(.+?)은\(는\) (\d+)장의 카드를 교체했습니다\.", text)
            if draw_match:
                lines.append(("sys", "%s는 카드 %s장을 교체했다." % (display_actor(draw_match.group(1)), draw_match.group(2))))
                continue
            if text.endswith("은(는) 교체 없이 진행했습니다."):
                actor = display_actor(text.split("은(는) 교체 없이 진행했습니다.", 1)[0])
                lines.append(("sys", "%s는 교체 없이 진행했다." % actor))
                continue
            if text == "당신은 교체 없이 진행했습니다.":
                lines.append(("sys", "플레이어는 교체 없이 진행했다."))
                continue
            player_draw_match = re.match(r"당신은 (\d+)장의 카드를 교체했습니다\.", text)
            if player_draw_match:
                lines.append(("sys", "플레이어는 카드 %s장을 교체했다." % player_draw_match.group(1)))
                continue
        return lines

    def _event_narration_lines(event_name, messages=None):
        """
        현재 단계와 결과를 설명하는 시스템 나레이션을 만든다.

        Args:
            event_name: 현재 이벤트 이름이다.
            messages: 직전 처리 결과 로그 목록이다.

        Returns:
            `(speaker_key, text)` 튜플 목록이다.
        """

        match = get_poker_match()
        lines = []
        messages = messages or []

        if event_name == "match_intro":
            return [("sys", "매치가 시작됐다. 곧 첫 라운드가 열린다.")]

        if event_name == "round_start":
            return [("sys", "라운드 %d 시작. 먼저 플레이어가 체크 또는 베팅 10칩 중 하나를 고른다." % match.hand_no)]

        if event_name == "betting":
            return []

        if event_name == "draw":
            if match.phase == "betting2":
                return [("sys", "드로우가 끝났다. 두 번째 베팅이 시작됐고, 다시 플레이어가 먼저 행동한다.")]
            return [("sys", "첫 번째 베팅이 끝났다. 지금은 드로우 단계다.")]

        if event_name == "round_end":
            if not match.round_summary:
                return [("sys", "라운드가 끝났다.")]
            winner = match.round_summary["winner"]
            pot = match.round_summary["pot"]
            if match.round_summary.get("ended_by_fold"):
                if match.round_summary.get("player_folded"):
                    return [("sys", "플레이어가 폴드했고, %s가 팟 %d칩을 가져갔다." % (winner, pot))]
                if match.round_summary.get("bot_folded"):
                    return [("sys", "%s가 폴드했고, 플레이어가 팟 %d칩을 가져갔다." % (match.bot.name, pot))]
            return [("sys", "라운드 종료. 승자는 %s, 팟은 %d칩이다." % (winner, pot))]

        if event_name == "match_end":
            if match.player.stack > match.bot.stack:
                return [("sys", "매치 종료. 플레이어가 최종 승리했다.")]
            if match.player.stack < match.bot.stack:
                return [("sys", "매치 종료. %s가 최종 승리했다." % match.bot.name)]
            return [("sys", "매치 종료. 무승부다.")]

        return lines

    def play_dialogue_event(event_name, messages=None):
        """
        현재 이벤트에 맞는 시스템 나레이션을 전용 배경 화면 위에서 순서대로 출력한다.

        Args:
            event_name: 대사 이벤트 이름이다.
            messages: 직전 처리 결과 로그 목록이다.
        """

        summary_lines = _action_summary_lines(messages)
        lines = _event_narration_lines(event_name, messages)

        renpy.show_screen(
            "poker_dialogue_backdrop",
            video_name=get_poker_dialogue_background_name(event_name),
        )

        speaker_map = {
            "sys": store.system_speaker,
            "narrator": None,
        }

        for speaker_key, text in summary_lines + lines:
            speaker = speaker_map.get(speaker_key)
            safe_text = _escape_renpy_say_text(text)
            if speaker is None:
                renpy.say(None, safe_text)
            else:
                renpy.say(speaker, safe_text)

        renpy.hide_screen("poker_dialogue_backdrop")
