"""규칙 기반 스크립트봇 판단을 별도 모듈로 분리한다."""

from __future__ import annotations

import random
from collections import Counter

from backend.poker_hands import RANK_VALUES, evaluate_hand


class SimpleScriptBot:
    """
    LLM 없이도 한 라운드를 끝까지 진행할 수 있는 규칙 기반 상대다.

    Args:
        없음.

    Returns:
        없음.
    """

    def choose_open_action(self, hand, phase, bet_size):
        """
        베팅을 먼저 열 차례일 때 체크와 베팅 중 하나를 고른다.

        Args:
            hand: 현재 봇 손패 목록이다.
            phase: 현재 베팅 페이즈 이름이다.
            bet_size: 기본 베팅 크기다.

        Returns:
            `check` 또는 `bet` 문자열이다.
        """

        rank_value, _, _ = evaluate_hand(hand)
        if rank_value >= 1:
            return "bet"
        if phase == "betting2" and random.random() < 0.2:
            return "bet"
        return "check"

    def choose_response_action(self, hand, phase, to_call, can_raise, raise_size):
        """
        상대 베팅에 대응할 콜, 레이즈, 폴드 중 하나를 고른다.

        Args:
            hand: 현재 봇 손패 목록이다.
            phase: 현재 베팅 페이즈 이름이다.
            to_call: 콜에 필요한 금액이다.
            can_raise: 현재 레이즈 가능 여부다.
            raise_size: 한 번 올릴 기본 레이즈 크기다.

        Returns:
            `call`, `raise`, `fold` 중 하나의 행동 문자열이다.
        """

        rank_value, tiebreak, _ = evaluate_hand(hand)
        high_card = max(tiebreak) if tiebreak else 0
        if can_raise and rank_value >= 2:
            return "raise"
        if can_raise and rank_value == 1 and high_card >= 11 and random.random() < 0.35:
            return "raise"
        if rank_value >= 1:
            return "call"
        if phase == "betting1" and high_card >= 13 and to_call <= raise_size and random.random() < 0.45:
            return "call"
        if phase == "betting2" and high_card >= 14 and to_call <= raise_size * 2 and random.random() < 0.2:
            return "call"
        return "fold"

    def choose_discards(self, hand, max_discards):
        """
        현재 손패에서 버릴 카드 인덱스를 계산한다.

        Args:
            hand: 현재 봇 손패 목록이다.
            max_discards: 이번 드로우에서 버릴 수 있는 최대 장수다.

        Returns:
            버릴 카드 인덱스 목록이다.
        """

        rank_value, _, _ = evaluate_hand(hand)
        values = [RANK_VALUES[rank] for rank, _ in hand]
        counts = Counter(values)

        if rank_value >= 4:
            return []
        if rank_value == 3:
            trip_value = [value for value, count in counts.items() if count == 3][0]
            return [index for index, card in enumerate(hand) if RANK_VALUES[card[0]] != trip_value][:max_discards]
        if rank_value == 2:
            kicker_value = [value for value, count in counts.items() if count == 1][0]
            return [index for index, card in enumerate(hand) if RANK_VALUES[card[0]] == kicker_value][:1]
        if rank_value == 1:
            pair_value = [value for value, count in counts.items() if count == 2][0]
            return [index for index, card in enumerate(hand) if RANK_VALUES[card[0]] != pair_value][:max_discards]

        sorted_indexes = sorted(
            range(len(hand)),
            key=lambda idx: RANK_VALUES[hand[idx][0]],
        )
        return sorted_indexes[:max_discards]
