"""카드 표현, 덱 생성, 족보 평가처럼 포커 공용 규칙을 모아 둔다."""

from __future__ import annotations

import random
from collections import Counter


RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
SUITS = ["Hearts", "Diamonds", "Clubs", "Spades"]
RANK_VALUES = {rank: index + 2 for index, rank in enumerate(RANKS)}
SUIT_NAMES_KO = {
    "Hearts": "하트",
    "Diamonds": "다이아",
    "Clubs": "클로버",
    "Spades": "스페이드",
}
HAND_NAMES_KO = {
    9: "로열 플러시",
    8: "스트레이트 플러시",
    7: "포카드",
    6: "풀하우스",
    5: "플러시",
    4: "스트레이트",
    3: "트리플",
    2: "투페어",
    1: "원페어",
    0: "하이카드",
}


def format_card_ko(card):
    """
    카드 한 장을 화면과 로그에서 쓰는 한국어 문자열로 바꾼다.

    Args:
        card: `(rank, suit)` 형태의 카드 튜플이다.

    Returns:
        `하트 Ace` 같은 한국어 카드 문자열이다.
    """

    rank, suit = card
    return "%s %s" % (SUIT_NAMES_KO[suit], rank)


def format_cards_ko(cards):
    """
    카드 목록을 사람이 읽기 쉬운 한국어 문자열로 합친다.

    Args:
        cards: 카드 튜플 목록이다.

    Returns:
        카드 여러 장을 쉼표로 이어 붙인 한국어 문자열이다.
    """

    return ", ".join(format_card_ko(card) for card in cards)


def card_image_path(card, state="idle"):
    """
    카드 한 장에 대응하는 Ren'Py 이미지 경로를 계산한다.

    Args:
        card: `(rank, suit)` 형태의 카드 튜플이다.
        state: 카드 표시 상태 이름이다.

    Returns:
        Ren'Py 이미지 리소스 경로 문자열이다.
    """

    rank, suit = card
    return "images/minigames/poker_minigame/%s_%s_%s.png" % (rank, suit.lower(), state)


def create_deck():
    """
    셔플된 표준 52장 덱을 만든다.

    Args:
        없음.

    Returns:
        무작위로 섞인 카드 튜플 목록이다.
    """

    deck = [(rank, suit) for rank in RANKS for suit in SUITS]
    random.shuffle(deck)
    return deck


def straight_high(values):
    """
    스트레이트면 가장 높은 값을, 아니면 None을 돌려준다.

    Args:
        values: 손패 숫자 값 목록이다.

    Returns:
        스트레이트 최고값 또는 None이다.
    """

    unique_values = sorted(set(values))
    if len(unique_values) != 5:
        return None
    if unique_values == [2, 3, 4, 5, 14]:
        return 5
    if unique_values[-1] - unique_values[0] == 4:
        return unique_values[-1]
    return None


def evaluate_hand(hand):
    """
    5장 손패의 족보, 타이브레이커, 한국어 족보명을 계산한다.

    Args:
        hand: 5장 카드 튜플 목록이다.

    Returns:
        `(rank_score, tiebreak_tuple, hand_name_ko)` 형태의 평가 결과다.
    """

    if len(hand) != 5:
        return 0, tuple(), "미정"

    values = [RANK_VALUES[rank] for rank, _ in hand]
    suits = [suit for _, suit in hand]
    counts = Counter(values)
    grouped_values = sorted(
        counts.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )
    is_flush = len(set(suits)) == 1
    straight = straight_high(values)

    if is_flush and straight == 14 and sorted(values) == [10, 11, 12, 13, 14]:
        return 9, (14,), HAND_NAMES_KO[9]
    if is_flush and straight:
        return 8, (straight,), HAND_NAMES_KO[8]
    if grouped_values[0][1] == 4:
        quad = grouped_values[0][0]
        kicker = [value for value in values if value != quad][0]
        return 7, (quad, kicker), HAND_NAMES_KO[7]
    if grouped_values[0][1] == 3 and grouped_values[1][1] == 2:
        return 6, (grouped_values[0][0], grouped_values[1][0]), HAND_NAMES_KO[6]
    if is_flush:
        return 5, tuple(sorted(values, reverse=True)), HAND_NAMES_KO[5]
    if straight:
        return 4, (straight,), HAND_NAMES_KO[4]
    if grouped_values[0][1] == 3:
        trip = grouped_values[0][0]
        kickers = sorted([value for value in values if value != trip], reverse=True)
        return 3, tuple([trip] + kickers), HAND_NAMES_KO[3]
    if grouped_values[0][1] == 2 and grouped_values[1][1] == 2:
        pair_values = sorted([value for value, count in counts.items() if count == 2], reverse=True)
        kicker = [value for value, count in counts.items() if count == 1][0]
        return 2, tuple(pair_values + [kicker]), HAND_NAMES_KO[2]
    if grouped_values[0][1] == 2:
        pair_value = grouped_values[0][0]
        kickers = sorted([value for value in values if value != pair_value], reverse=True)
        return 1, tuple([pair_value] + kickers), HAND_NAMES_KO[1]
    return 0, tuple(sorted(values, reverse=True)), HAND_NAMES_KO[0]


def compare_hands(player_hand, bot_hand):
    """
    두 손패를 비교해 플레이어, 봇, 무승부 중 하나를 판정한다.

    Args:
        player_hand: 플레이어 손패 목록이다.
        bot_hand: 봇 손패 목록이다.

    Returns:
        `(winner, player_rank, bot_rank)` 형태의 비교 결과다.
    """

    player_rank = evaluate_hand(player_hand)
    bot_rank = evaluate_hand(bot_hand)
    if player_rank[0] > bot_rank[0]:
        return "player", player_rank, bot_rank
    if player_rank[0] < bot_rank[0]:
        return "bot", player_rank, bot_rank
    if player_rank[1] > bot_rank[1]:
        return "player", player_rank, bot_rank
    if player_rank[1] < bot_rank[1]:
        return "bot", player_rank, bot_rank
    return "tie", player_rank, bot_rank
