import random
from collections import Counter
from dataclasses import dataclass, field

from backend.llm_agent import LocalLLMAgent
from backend.policy_loop import PolicyLoop


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
PHASE_NAMES_KO = {
    "betting1": "첫 번째 베팅",
    "draw": "드로우",
    "betting2": "두 번째 베팅",
    "showdown": "쇼다운",
    "finished": "라운드 종료",
}


@dataclass
class PlayerState:
    """PlayerState, 한 플레이어의 현재 포커 상태를 담는다.

    Args:
        name: 플레이어 이름.
        stack: 현재 칩 수.
        hand: 현재 손패 목록.
        folded: 폴드 여부.

    Returns:
        PlayerState: 플레이어 상태 객체.
    """

    name: str
    stack: int
    hand: list = field(default_factory=list)
    folded: bool = False


def format_card_ko(card):
    """format_card_ko, 카드 한 장을 한국어 문자열로 변환한다.

    Args:
        card: `(rank, suit)` 형식의 카드 튜플.

    Returns:
        str: 한국어 카드 표시 문자열.
    """

    rank, suit = card
    return "%s %s" % (SUIT_NAMES_KO[suit], rank)


def format_cards_ko(cards):
    """format_cards_ko, 카드 목록을 한국어 문자열로 합친다.

    Args:
        cards: 카드 튜플 목록.

    Returns:
        str: 카드 목록 표시 문자열.
    """

    return ", ".join(format_card_ko(card) for card in cards)


def card_image_path(card, state="idle"):
    """card_image_path, 카드 이미지 리소스 경로를 계산한다.

    Args:
        card: `(rank, suit)` 형식의 카드 튜플.
        state: 카드 이미지 상태 문자열.

    Returns:
        str: Ren'Py 이미지 경로 문자열.
    """

    rank, suit = card
    return "images/minigames/poker_minigame/%s_%s_%s.png" % (rank, suit.lower(), state)


def create_deck():
    """create_deck, 셔플된 52장 덱을 생성한다.

    Args:
        없음.

    Returns:
        list: 셔플된 카드 튜플 목록.
    """

    deck = [(rank, suit) for rank in RANKS for suit in SUITS]
    random.shuffle(deck)
    return deck


def straight_high(values):
    """straight_high, 스트레이트의 최고 숫자를 계산한다.

    Args:
        values: 카드 숫자 값 목록.

    Returns:
        int | None: 스트레이트 최고값 또는 스트레이트가 아닐 때 None.
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
    """evaluate_hand, 5장 손패의 족보와 타이브레이커를 계산한다.

    Args:
        hand: 카드 5장 튜플 목록.

    Returns:
        tuple: `(족보 순위, 타이브레이커 튜플, 한국어 족보명)`.
    """

    if len(hand) != 5:
        return 0, tuple(), "미정"

    values = [RANK_VALUES[rank] for rank, _ in hand]
    suits = [suit for _, suit in hand]
    counts = Counter(values)
    by_count_then_value = sorted(
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
    if by_count_then_value[0][1] == 4:
        quad = by_count_then_value[0][0]
        kicker = [value for value in values if value != quad][0]
        return 7, (quad, kicker), HAND_NAMES_KO[7]
    if by_count_then_value[0][1] == 3 and by_count_then_value[1][1] == 2:
        return 6, (by_count_then_value[0][0], by_count_then_value[1][0]), HAND_NAMES_KO[6]
    if is_flush:
        return 5, tuple(sorted(values, reverse=True)), HAND_NAMES_KO[5]
    if straight:
        return 4, (straight,), HAND_NAMES_KO[4]
    if by_count_then_value[0][1] == 3:
        trip = by_count_then_value[0][0]
        kickers = sorted([value for value in values if value != trip], reverse=True)
        return 3, tuple([trip] + kickers), HAND_NAMES_KO[3]
    if by_count_then_value[0][1] == 2 and by_count_then_value[1][1] == 2:
        pair_values = sorted([value for value, count in counts.items() if count == 2], reverse=True)
        kicker = [value for value, count in counts.items() if count == 1][0]
        return 2, tuple(pair_values + [kicker]), HAND_NAMES_KO[2]
    if by_count_then_value[0][1] == 2:
        pair_value = by_count_then_value[0][0]
        kickers = sorted([value for value in values if value != pair_value], reverse=True)
        return 1, tuple([pair_value] + kickers), HAND_NAMES_KO[1]
    return 0, tuple(sorted(values, reverse=True)), HAND_NAMES_KO[0]


def compare_hands(player_hand, bot_hand):
    """compare_hands, 두 손패를 비교해 승자를 판정한다.

    Args:
        player_hand: 플레이어 손패.
        bot_hand: 봇 손패.

    Returns:
        tuple: `(승자 식별자, 플레이어 평가 결과, 봇 평가 결과)`.
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


class SimpleScriptBot:
    """SimpleScriptBot, 현재 구현에서 사용하는 규칙 기반 스크립트 상대다.

    Args:
        없음.

    Returns:
        SimpleScriptBot: 스크립트봇 객체.
    """

    def choose_open_action(self, hand, phase, bet_size):
        """choose_open_action, 베팅을 먼저 열 때 행동을 결정한다.

        Args:
            hand: 봇 손패.
            phase: 현재 베팅 페이즈.
            bet_size: 고정 베팅 금액.

        Returns:
            str: `check` 또는 `bet`.
        """

        rank_value, _, _ = evaluate_hand(hand)
        if rank_value >= 1:
            return "bet"
        if phase == "betting2" and random.random() < 0.2:
            return "bet"
        return "check"

    def choose_response_action(self, hand, phase, to_call, can_raise, raise_size):
        """choose_response_action, 상대 베팅에 대한 응답 행동을 결정한다.

        Args:
            hand: 봇 손패.
            phase: 현재 베팅 페이즈.
            to_call: 현재 맞춰야 할 금액.
            can_raise: 현재 레이즈 가능 여부.
            raise_size: 현재 레이즈 단위 금액.

        Returns:
            str: `call`, `raise`, `fold` 중 하나.
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
        """choose_discards, 드로우 단계에서 버릴 카드 인덱스를 고른다.

        Args:
            hand: 봇 손패.
            max_discards: 최대 교체 가능 장수.

        Returns:
            list: 버릴 카드 인덱스 목록.
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


class PokerMatch:
    """PokerMatch, v1 2인 5드로우 포커 라운드 진행을 관리한다.

    Args:
        config: 백엔드 설정 객체.
        memory_manager: 기억 저장 객체.
        replay_logger: 리플레이 저장 객체.
        player_name: 인간 플레이어 이름.
        bot_name: 상대 봇 이름.

    Returns:
        PokerMatch: 라운드 진행 객체.
    """

    def __init__(self, config, memory_manager, replay_logger, player_name="플레이어", bot_name="스크립트봇"):
        self.config = config
        self.memory_manager = memory_manager
        self.replay_logger = replay_logger
        self.policy_loop = PolicyLoop(memory_manager)
        self.player = PlayerState(player_name, config.starting_stack)
        self.bot = PlayerState(bot_name, config.starting_stack)
        self.script_bot = SimpleScriptBot()
        self.llm_agent = LocalLLMAgent(
            config.local_llm_path,
            config.llm_runner_python,
            memory_manager,
            config.llm_backend,
            config.llm_quantization,
        )
        self.bot_mode = config.bot_mode
        self.hand_no = 0
        self.phase = "finished"
        self.pot = 0
        self.deck = []
        self.current_bet = 0
        self.awaiting_response = False
        self.pending_bettor = None
        self.current_actor = "player"
        self.player_contribution = 0
        self.bot_contribution = 0
        self.raises_in_round = 0
        self.consecutive_checks = 0
        self.round_over = False
        self.action_log = []
        self.public_log = []
        self.round_summary = None
        self.latest_feedback = None
        self.last_llm_reason = ""
        self._apply_bot_mode_name()

    def can_continue_match(self):
        """can_continue_match, 다음 라운드를 시작할 칩이 남아 있는지 확인한다.

        Args:
            없음.

        Returns:
            bool: 다음 라운드 시작 가능 여부.
        """

        return self.player.stack >= self.config.ante and self.bot.stack >= self.config.ante

    def to_snapshot(self):
        """to_snapshot, 현재 매치 상태를 저장 가능한 사전으로 변환한다.

        Args:
            없음.

        Returns:
            dict: 세이브 파일에 넣을 수 있는 단순 상태 사전.
        """

        return {
            "player_name": self.player.name,
            "bot_name": self.bot.name,
            "player_stack": self.player.stack,
            "bot_stack": self.bot.stack,
            "player_hand": list(self.player.hand),
            "bot_hand": list(self.bot.hand),
            "player_folded": self.player.folded,
            "bot_folded": self.bot.folded,
            "hand_no": self.hand_no,
            "phase": self.phase,
            "pot": self.pot,
            "deck": list(self.deck),
            "current_bet": self.current_bet,
            "awaiting_response": self.awaiting_response,
            "pending_bettor": self.pending_bettor,
            "current_actor": self.current_actor,
            "player_contribution": self.player_contribution,
            "bot_contribution": self.bot_contribution,
            "raises_in_round": self.raises_in_round,
            "consecutive_checks": self.consecutive_checks,
            "round_over": self.round_over,
            "action_log": list(self.action_log),
            "public_log": list(self.public_log),
            "round_summary": self.round_summary,
            "latest_feedback": self.latest_feedback,
            "bot_mode": self.bot_mode,
            "last_llm_reason": self.last_llm_reason,
            "llm_backend": self.config.llm_backend,
            "llm_quantization": self.config.llm_quantization,
        }

    @classmethod
    def from_snapshot(cls, config, memory_manager, replay_logger, snapshot):
        """from_snapshot, 저장된 스냅샷으로 매치 객체를 복원한다.

        Args:
            config: 백엔드 설정 객체.
            memory_manager: 기억 저장 객체.
            replay_logger: 리플레이 저장 객체.
            snapshot: 세이브에서 읽은 상태 사전.

        Returns:
            PokerMatch: 복원된 매치 객체.
        """

        match = cls(
            config,
            memory_manager,
            replay_logger,
            player_name=snapshot["player_name"],
            bot_name=snapshot["bot_name"],
        )
        match.player.stack = snapshot["player_stack"]
        match.bot.stack = snapshot["bot_stack"]
        match.player.hand = list(snapshot["player_hand"])
        match.bot.hand = list(snapshot["bot_hand"])
        match.player.folded = snapshot["player_folded"]
        match.bot.folded = snapshot["bot_folded"]
        match.hand_no = snapshot["hand_no"]
        match.phase = snapshot["phase"]
        match.pot = snapshot["pot"]
        match.deck = list(snapshot["deck"])
        match.current_bet = snapshot["current_bet"]
        match.awaiting_response = snapshot.get("awaiting_response", False)
        match.pending_bettor = snapshot.get("pending_bettor")
        match.current_actor = snapshot.get("current_actor", "player")
        match.player_contribution = snapshot.get("player_contribution", 0)
        match.bot_contribution = snapshot.get("bot_contribution", 0)
        match.raises_in_round = snapshot.get("raises_in_round", 0)
        match.consecutive_checks = snapshot.get("consecutive_checks", 0)
        match.round_over = snapshot["round_over"]
        match.action_log = list(snapshot["action_log"])
        match.public_log = list(snapshot.get("public_log", []))
        match.round_summary = snapshot["round_summary"]
        match.latest_feedback = snapshot["latest_feedback"]
        match.bot_mode = snapshot.get("bot_mode", config.bot_mode)
        match.last_llm_reason = snapshot.get("last_llm_reason", "")
        match.config.llm_backend = snapshot.get("llm_backend", config.llm_backend)
        match.config.llm_quantization = snapshot.get("llm_quantization", config.llm_quantization)
        match.llm_agent.reconfigure(
            llm_backend=match.config.llm_backend,
            llm_quantization=match.config.llm_quantization,
        )
        match._apply_bot_mode_name()
        return match

    def phase_name_ko(self):
        """phase_name_ko, 현재 페이즈의 한국어 이름을 반환한다.

        Args:
            없음.

        Returns:
            str: 현재 페이즈의 한국어 이름.
        """

        return PHASE_NAMES_KO.get(self.phase, self.phase)

    def _apply_bot_mode_name(self):
        """_apply_bot_mode_name, 현재 봇 모드에 맞는 표시 이름을 적용한다.

        Args:
            없음.

        Returns:
            None: 봇 표시 이름을 갱신한다.
        """

        if self.bot_mode == "llm_npc":
            self.bot.name = "사야"
        else:
            self.bot.name = "스크립트봇"

    def set_bot_mode(self, bot_mode):
        """set_bot_mode, 현재 매치에서 사용할 상대 AI 모드를 변경한다.

        Args:
            bot_mode: `script_bot` 또는 `llm_npc`.

        Returns:
            None: 봇 모드와 표시 이름을 갱신한다.
        """

        self.bot_mode = bot_mode
        self.config.bot_mode = bot_mode
        self._apply_bot_mode_name()

    def get_bot_mode_label(self):
        """get_bot_mode_label, 현재 상대 AI 모드의 표시명을 반환한다.

        Args:
            없음.

        Returns:
            str: UI에 표시할 상대 AI 모드 문자열.
        """

        if self.bot_mode == "llm_npc":
            return "LLM NPC"
        return "스크립트봇"

    def get_llm_status_text(self):
        """get_llm_status_text, 현재 LLM 워커 상태 설명을 반환한다.

        Args:
            없음.

        Returns:
            str: LLM 상태 문자열.
        """

        return self.llm_agent.last_status

    def get_llm_backend_label(self):
        """get_llm_backend_label, 현재 LLM 추론 백엔드 표시명을 반환한다.

        Args:
            없음.

        Returns:
            str: UI에 표시할 백엔드 문자열.
        """

        active_backend = self.llm_agent.__class__._worker_backend or self.config.llm_backend
        active_quantization = self.llm_agent.__class__._worker_quantization or self.config.llm_quantization

        if active_backend == "vllm":
            if active_quantization == "bitsandbytes":
                return "vLLM 4비트"
            return "vLLM"
        return "Transformers"

    def format_bot_hand_for_prompt(self):
        """format_bot_hand_for_prompt, LLM 프롬프트용 봇 손패 문자열 목록을 반환한다.

        Args:
            없음.

        Returns:
            list: 한국어 카드 문자열 목록.
        """

        return [format_card_ko(card) for card in self.bot.hand]

    def start_new_round(self):
        """start_new_round, 새 포커 라운드를 초기화하고 시작 로그를 만든다.

        Args:
            없음.

        Returns:
            list: 라운드 시작 로그 문자열 목록.
        """

        if not self.can_continue_match():
            self.round_over = True
            self.phase = "finished"
            self.action_log = ["한쪽의 칩이 부족해 더 이상 라운드를 시작할 수 없습니다."]
            self.public_log = ["한쪽의 칩이 부족해 더 이상 라운드를 시작할 수 없습니다."]
            return self.action_log

        self.hand_no += 1
        self.deck = create_deck()
        self.pot = 0
        self.round_over = False
        self.action_log = []
        self.public_log = []
        self.round_summary = None
        self.latest_feedback = None
        self.player.folded = False
        self.bot.folded = False
        self.player.hand = [self.deck.pop() for _ in range(5)]
        self.bot.hand = [self.deck.pop() for _ in range(5)]

        self.player.stack -= self.config.ante
        self.bot.stack -= self.config.ante
        self.pot = self.config.ante * 2

        public_start = "라운드 %d 시작. 각자 %d칩 앤티를 냈습니다." % (self.hand_no, self.config.ante)
        self.action_log.append(public_start)
        self.public_log.append(public_start)
        self.action_log.append("당신의 시작 손패: %s" % format_cards_ko(self.player.hand))
        self._start_betting_round("betting1")
        return list(self.action_log)

    def get_player_hand(self):
        """get_player_hand, 플레이어 손패를 반환한다.

        Args:
            없음.

        Returns:
            list: 플레이어 카드 목록.
        """

        return list(self.player.hand)

    def get_bot_hand(self, reveal=False):
        """get_bot_hand, 봇 손패를 반환하거나 비공개 카드로 가린다.

        Args:
            reveal: 실제 손패 공개 여부.

        Returns:
            list: 실제 손패 또는 숨김 표시 카드 목록.
        """

        if reveal or self.round_over:
            return list(self.bot.hand)
        return [("Hidden", "Back")] * len(self.bot.hand)

    def get_player_hand_name(self):
        """get_player_hand_name, 플레이어 현재 족보명을 반환한다.

        Args:
            없음.

        Returns:
            str: 한국어 족보명.
        """

        return evaluate_hand(self.player.hand)[2]

    def get_bot_hand_name(self):
        """get_bot_hand_name, 봇 현재 족보명을 반환한다.

        Args:
            없음.

        Returns:
            str: 한국어 족보명.
        """

        return evaluate_hand(self.bot.hand)[2]

    def is_match_finished(self):
        """is_match_finished, 현재 라운드 종료 후 매치가 끝났는지 확인한다.

        Args:
            없음.

        Returns:
            bool: 다음 라운드를 시작할 수 없으면 True.
        """

        return self.round_over and not self.can_continue_match()

    def get_round_result_title(self):
        """get_round_result_title, 라운드 종료 화면 제목을 반환한다.

        Args:
            없음.

        Returns:
            str: 승패에 맞는 종료 제목 문자열.
        """

        if not self.round_summary:
            return "라운드 종료"

        winner = self.round_summary["winner"]
        if winner == self.player.name:
            return "라운드 승리"
        if winner == self.bot.name:
            return "라운드 패배"
        return "무승부"

    def get_round_result_message(self):
        """get_round_result_message, 종료 화면의 핵심 결과 문구를 반환한다.

        Args:
            없음.

        Returns:
            str: 승패와 종료 방식이 정리된 결과 문구.
        """

        if not self.round_summary:
            return "아직 종료된 라운드가 없습니다."

        winner = self.round_summary["winner"]
        ended_by_fold = self.round_summary["ended_by_fold"]

        if winner == "무승부":
            base_message = "양쪽이 같은 강도의 패를 만들어 팟을 나눠 가졌습니다."
        elif winner == self.player.name:
            base_message = "당신이 이번 라운드의 팟 %d칩을 가져갔습니다." % self.round_summary["pot"]
        else:
            base_message = "%s이(가) 이번 라운드의 팟 %d칩을 가져갔습니다." % (
                self.bot.name,
                self.round_summary["pot"],
            )

        if ended_by_fold:
            return "%s 폴드로 라운드가 종료되었습니다." % base_message
        return "%s 쇼다운에서 양쪽 패를 비교한 결과입니다." % base_message

    def get_match_result_message(self):
        """get_match_result_message, 매치 종료 여부를 설명하는 문구를 반환한다.

        Args:
            없음.

        Returns:
            str: 다음 라운드 가능 여부 또는 매치 종료 문구.
        """

        if self.is_match_finished():
            if self.player.stack < self.config.ante:
                return "당신의 스택이 앤티보다 부족해 매치가 종료되었습니다."
            if self.bot.stack < self.config.ante:
                return "%s의 스택이 앤티보다 부족해 매치가 종료되었습니다." % self.bot.name
            return "더 이상 다음 라운드를 시작할 수 없어 매치가 종료되었습니다."
        return "다음 라운드를 계속 진행할 수 있습니다."

    def get_recent_log_text(self, limit=8):
        """get_recent_log_text, 최근 로그를 화면 표시용 문자열로 합친다.

        Args:
            limit: 표시할 최대 로그 수.

        Returns:
            str: 줄바꿈으로 합쳐진 최근 로그 문자열.
        """

        return "\n".join(self.action_log[-limit:])

    def get_public_log_lines(self, limit=8):
        """get_public_log_lines, 공개 정보만 담긴 최근 로그 목록을 반환한다.

        Args:
            limit: 표시할 최대 공개 로그 수.

        Returns:
            list: 공개 진행 정보 문자열 목록.
        """

        return list(self.public_log[-limit:])

    def is_player_turn(self):
        """is_player_turn, 현재 베팅 페이즈에서 플레이어 차례인지 확인한다.

        Args:
            없음.

        Returns:
            bool: 플레이어 차례면 True.
        """

        return self.phase in ("betting1", "betting2") and self.current_actor == "player" and not self.round_over

    def get_player_amount_to_call(self):
        """get_player_amount_to_call, 플레이어가 맞춰야 할 현재 금액을 반환한다.

        Args:
            없음.

        Returns:
            int: 플레이어가 콜하기 위해 더 내야 하는 칩 수.
        """

        return max(0, self.current_bet - self.player_contribution)

    def get_bot_amount_to_call(self):
        """get_bot_amount_to_call, 봇이 맞춰야 할 현재 금액을 반환한다.

        Args:
            없음.

        Returns:
            int: 봇이 콜하기 위해 더 내야 하는 칩 수.
        """

        return max(0, self.current_bet - self.bot_contribution)

    def get_player_available_actions(self):
        """get_player_available_actions, 현재 플레이어가 선택 가능한 행동을 계산한다.

        Args:
            없음.

        Returns:
            list: 현재 플레이어에게 합법인 행동 문자열 목록.
        """

        if not self.is_player_turn():
            return []
        return self._get_available_actions("player")

    def can_player_raise(self):
        """can_player_raise, 현재 플레이어가 레이즈 가능한지 확인한다.

        Args:
            없음.

        Returns:
            bool: 플레이어 레이즈 가능 여부.
        """

        return "raise" in self.get_player_available_actions()

    def get_raise_total_amount(self):
        """get_raise_total_amount, 플레이어가 레이즈 시 이번 턴에 내야 할 총액을 반환한다.

        Args:
            없음.

        Returns:
            int: 콜 금액과 추가 레이즈를 합친 총 지불 금액.
        """

        return self.get_player_amount_to_call() + self.config.fixed_bet

    def get_betting_status_text(self):
        """get_betting_status_text, 현재 베팅 라운드 정보를 설명하는 문구를 반환한다.

        Args:
            없음.

        Returns:
            str: 맞춰야 할 금액과 남은 레이즈 횟수 설명.
        """

        if self.phase not in ("betting1", "betting2"):
            return ""

        to_call = self.get_player_amount_to_call()
        raises_left = self.config.max_raises_per_round - self.raises_in_round
        if to_call > 0:
            return "현재 콜 금액: %d칩 / 남은 레이즈: %d회" % (to_call, max(0, raises_left))
        return "현재 체크 가능 / 남은 레이즈: %d회" % max(0, raises_left)

    def _start_betting_round(self, phase):
        """_start_betting_round, 베팅 라운드 상태를 초기화한다.

        Args:
            phase: 시작할 베팅 페이즈 문자열.

        Returns:
            None: 베팅 상태를 초기화한다.
        """

        self.phase = phase
        self.current_bet = 0
        self.awaiting_response = False
        self.pending_bettor = None
        self.current_actor = "player"
        self.player_contribution = 0
        self.bot_contribution = 0
        self.raises_in_round = 0
        self.consecutive_checks = 0

    def _get_available_actions(self, actor_name):
        """_get_available_actions, 지정 플레이어 기준 합법 행동 목록을 계산한다.

        Args:
            actor_name: `player` 또는 `bot`.

        Returns:
            list: 현재 선택 가능한 행동 문자열 목록.
        """

        actor = self.player if actor_name == "player" else self.bot
        contribution = self.player_contribution if actor_name == "player" else self.bot_contribution
        to_call = max(0, self.current_bet - contribution)
        actions = []

        if to_call == 0:
            actions.append("check")
            if actor.stack >= self.config.fixed_bet:
                actions.append("bet")
            return actions

        actions.append("fold")
        if actor.stack >= to_call:
            actions.append("call")
        if (
            actor.stack >= to_call + self.config.fixed_bet
            and self.raises_in_round < self.config.max_raises_per_round
        ):
            actions.append("raise")
        return actions

    def _deduct(self, actor, amount):
        """_deduct, 플레이어 칩을 차감하고 팟에 반영한다.

        Args:
            actor: 칩을 낼 플레이어 상태 객체.
            amount: 차감할 칩 수.

        Returns:
            None: 내부 상태만 갱신한다.
        """

        actor.stack -= amount
        self.pot += amount

    def _finish_by_fold(self, winner):
        """_finish_by_fold, 폴드로 끝난 라운드를 마감 처리한다.

        Args:
            winner: 폴드로 승리한 플레이어 상태 객체.

        Returns:
            None: 라운드 종료 상태를 갱신한다.
        """

        winner.stack += self.pot
        self.phase = "finished"
        self.round_over = True
        self._finalize_round_summary(winner_name=winner.name, folded=True)

    def _advance_after_betting(self):
        """_advance_after_betting, 베팅 완료 후 다음 페이즈로 진행한다.

        Args:
            없음.

        Returns:
            None: 다음 페이즈 또는 쇼다운으로 진행한다.
        """

        if self.phase == "betting1":
            self.phase = "draw"
            return ["드로우 단계로 넘어갑니다."]
        elif self.phase == "betting2":
            return self._resolve_showdown()
        return []

    def resolve_player_action(self, action):
        """resolve_player_action, 플레이어의 현재 베팅 행동을 적용한다.

        Args:
            action: 플레이어가 선택한 행동 문자열.

        Returns:
            list: 처리 결과 로그 문자열 목록.
        """

        if self.phase not in ("betting1", "betting2") or self.round_over or not self.is_player_turn():
            return ["지금은 그 행동을 할 수 없습니다."]
        if action not in self._get_available_actions("player"):
            return ["지금은 그 행동을 선택할 수 없습니다."]

        messages = self._apply_betting_action("player", action)
        if not self.round_over:
            messages.extend(self._run_bot_turns())
        return messages

    def _apply_betting_action(self, actor_name, action):
        """_apply_betting_action, 현재 베팅 라운드의 한 행동을 적용한다.

        Args:
            actor_name: 행동 주체 식별자.
            action: 적용할 행동 문자열.

        Returns:
            list: 적용 결과 로그 문자열 목록.
        """

        actor = self.player if actor_name == "player" else self.bot
        actor_label = "당신" if actor_name == "player" else self.bot.name
        other_actor = self.bot if actor_name == "player" else self.player
        to_call = self.get_player_amount_to_call() if actor_name == "player" else self.get_bot_amount_to_call()
        messages = []

        if action == "check":
            self.consecutive_checks += 1
            self.current_actor = "bot" if actor_name == "player" else "player"
            messages.append("%s이(가) 체크했습니다." % actor_label)
            if self.consecutive_checks >= 2:
                self.action_log.extend(messages)
                self.public_log.extend(messages)
                close_messages = self._advance_after_betting()
                if self.phase != "finished":
                    self.action_log.extend(close_messages)
                    self.public_log.extend(close_messages)
                messages.extend(close_messages)
                return messages
            self.action_log.extend(messages)
            self.public_log.extend(messages)
            return messages

        if action == "bet":
            self._deduct(actor, self.config.fixed_bet)
            if actor_name == "player":
                self.player_contribution += self.config.fixed_bet
                self.current_bet = self.player_contribution
                self.pending_bettor = "player"
            else:
                self.bot_contribution += self.config.fixed_bet
                self.current_bet = self.bot_contribution
                self.pending_bettor = "bot"
            self.awaiting_response = True
            self.consecutive_checks = 0
            self.current_actor = "bot" if actor_name == "player" else "player"
            messages.append("%s이(가) %d칩 베팅했습니다." % (actor_label, self.config.fixed_bet))
            self.action_log.extend(messages)
            self.public_log.extend(messages)
            return messages

        if action == "call":
            self._deduct(actor, to_call)
            if actor_name == "player":
                self.player_contribution += to_call
            else:
                self.bot_contribution += to_call
            messages.append("%s이(가) 콜했습니다." % actor_label)
            self.action_log.extend(messages)
            self.public_log.extend(messages)
            close_messages = self._advance_after_betting()
            if self.phase != "finished":
                self.action_log.extend(close_messages)
                self.public_log.extend(close_messages)
            messages.extend(close_messages)
            return messages

        if action == "raise":
            total_payment = to_call + self.config.fixed_bet
            self._deduct(actor, total_payment)
            if actor_name == "player":
                self.player_contribution += total_payment
                self.current_bet = self.player_contribution
                self.pending_bettor = "player"
            else:
                self.bot_contribution += total_payment
                self.current_bet = self.bot_contribution
                self.pending_bettor = "bot"
            self.awaiting_response = True
            self.raises_in_round += 1
            self.consecutive_checks = 0
            self.current_actor = "bot" if actor_name == "player" else "player"
            messages.append(
                "%s이(가) %d칩을 더 올려 총 %d칩이 되도록 레이즈했습니다." % (
                    actor_label,
                    self.config.fixed_bet,
                    self.current_bet,
                )
            )
            self.action_log.extend(messages)
            self.public_log.extend(messages)
            return messages

        if action == "fold":
            actor.folded = True
            messages.append("%s이(가) 폴드했습니다." % actor_label)
            self.action_log.extend(messages)
            self.public_log.extend(messages)
            self._finish_by_fold(other_actor)
            return messages

        return ["알 수 없는 행동입니다."]

    def _run_bot_turns(self):
        """_run_bot_turns, 플레이어 차례가 돌아오거나 페이즈가 끝날 때까지 봇 행동을 처리한다.

        Args:
            없음.

        Returns:
            list: 봇 행동과 결과 로그 문자열 목록.
        """

        messages = []
        while not self.round_over and self.phase in ("betting1", "betting2") and self.current_actor == "bot":
            actions = self._get_available_actions("bot")
            if self.bot_mode == "llm_npc":
                llm_choice = self.llm_agent.choose_action(self, actions)
                bot_action = llm_choice["action"]
                self.last_llm_reason = llm_choice.get("reason", "")
                llm_log = "[LLM NPC] %s 행동 선택: %s / 이유: %s" % (
                    self.bot.name,
                    bot_action,
                    self.last_llm_reason,
                )
                self.action_log.append(llm_log)
                self.public_log.append(llm_log)
                messages.append(llm_log)
            elif self.current_bet == 0:
                bot_action = self.script_bot.choose_open_action(self.bot.hand, self.phase, self.config.fixed_bet)
            else:
                bot_action = self.script_bot.choose_response_action(
                    self.bot.hand,
                    self.phase,
                    self.get_bot_amount_to_call(),
                    "raise" in actions,
                    self.config.fixed_bet,
                )
                self.last_llm_reason = ""

            if self.bot_mode != "llm_npc" and self.current_bet == 0:
                self.last_llm_reason = ""
            elif self.bot_mode != "llm_npc" and self.current_bet > 0:
                self.last_llm_reason = ""

            if bot_action not in actions:
                if "call" in actions:
                    bot_action = "call"
                elif "check" in actions:
                    bot_action = "check"
                else:
                    bot_action = "fold"

            messages.extend(self._apply_betting_action("bot", bot_action))
        return messages

    def resolve_draw_phase(self, discard_indexes):
        """resolve_draw_phase, 플레이어와 봇의 카드 교체를 처리한다.

        Args:
            discard_indexes: 플레이어가 교체할 카드 인덱스 목록.

        Returns:
            list: 드로우 결과 로그 문자열 목록.
        """

        messages = []
        if self.phase != "draw" or self.round_over:
            return ["지금은 드로우 단계가 아닙니다."]

        unique_indexes = sorted(set(discard_indexes))
        if len(unique_indexes) > self.config.max_discards:
            return ["최대 %d장까지만 교체할 수 있습니다." % self.config.max_discards]
        if any(index < 0 or index >= len(self.player.hand) for index in unique_indexes):
            return ["교체할 카드 선택이 올바르지 않습니다."]

        if unique_indexes:
            messages.append("당신은 %d장의 카드를 교체했습니다." % len(unique_indexes))
            self._replace_cards(self.player, unique_indexes)
        else:
            messages.append("당신은 교체 없이 진행했습니다.")

        if self.bot_mode == "llm_npc":
            draw_choice = self.llm_agent.choose_discards(self, self.config.max_discards)
            bot_discards = draw_choice["discard_indexes"]
            llm_draw_log = "[LLM NPC] %s 카드 교체 판단: %s / 이유: %s" % (
                self.bot.name,
                bot_discards,
                draw_choice.get("reason", ""),
            )
            self.action_log.append(llm_draw_log)
            self.public_log.append(llm_draw_log)
        else:
            bot_discards = self.script_bot.choose_discards(self.bot.hand, self.config.max_discards)
        if bot_discards:
            self._replace_cards(self.bot, bot_discards)
            messages.append("%s은(는) %d장의 카드를 교체했습니다." % (self.bot.name, len(bot_discards)))
        else:
            messages.append("%s은(는) 교체 없이 진행했습니다." % self.bot.name)

        messages.append("당신의 현재 손패: %s" % format_cards_ko(self.player.hand))
        self.action_log.extend(messages)
        self.public_log.extend([line for line in messages if not line.startswith("당신의 현재 손패:")])
        self._start_betting_round("betting2")
        return messages

    def _replace_cards(self, actor, discard_indexes):
        """_replace_cards, 지정한 카드 인덱스를 새 카드로 교체한다.

        Args:
            actor: 카드를 교체할 플레이어 상태 객체.
            discard_indexes: 교체할 카드 인덱스 목록.

        Returns:
            None: 손패를 내부적으로 교체한다.
        """

        for index in discard_indexes:
            actor.hand[index] = self.deck.pop()

    def _resolve_showdown(self):
        """_resolve_showdown, 쇼다운을 처리하고 승자를 정산한다.

        Args:
            없음.

        Returns:
            list: 쇼다운 결과 로그 문자열 목록.
        """

        result, player_rank, bot_rank = compare_hands(self.player.hand, self.bot.hand)
        self.phase = "showdown"
        messages = [
            "쇼다운입니다.",
            "당신의 손패: %s (%s)" % (format_cards_ko(self.player.hand), player_rank[2]),
            "%s의 손패: %s (%s)" % (self.bot.name, format_cards_ko(self.bot.hand), bot_rank[2]),
        ]

        if result == "player":
            self.player.stack += self.pot
            messages.append("당신이 이번 라운드를 가져갔습니다.")
            self.action_log.extend(messages)
            self._finalize_round_summary(self.player.name, folded=False)
        elif result == "bot":
            self.bot.stack += self.pot
            messages.append("%s이(가) 이번 라운드를 가져갔습니다." % self.bot.name)
            self.action_log.extend(messages)
            self._finalize_round_summary(self.bot.name, folded=False)
        else:
            split = self.pot // 2
            self.player.stack += split
            self.bot.stack += self.pot - split
            messages.append("무승부입니다. 팟을 나눠 가집니다.")
            self.action_log.extend(messages)
            self._finalize_round_summary("무승부", folded=False)
        return messages

    def _finalize_round_summary(self, winner_name, folded):
        """_finalize_round_summary, 라운드 결과 요약과 기억/리플레이를 저장한다.

        Args:
            winner_name: 승자 이름.
            folded: 폴드 종료 여부.

        Returns:
            None: 요약 저장과 메모리 업데이트를 수행한다.
        """

        self.round_over = True
        self.phase = "finished"
        self.round_summary = {
            "hand_no": self.hand_no,
            "winner": winner_name,
            "pot": self.pot,
            "player_name": self.player.name,
            "bot_name": self.bot.name,
            "player_hand_name": self.get_player_hand_name(),
            "bot_hand_name": self.get_bot_hand_name(),
            "player_stack": self.player.stack,
            "bot_stack": self.bot.stack,
            "bot_folded": self.bot.folded,
            "player_folded": self.player.folded,
            "ended_by_fold": folded,
            "log": list(self.action_log),
        }
        self.latest_feedback = self.policy_loop.persist_feedback(self.round_summary)
        self.replay_logger.append_round(self.round_summary)

    def get_round_summary_lines(self):
        """get_round_summary_lines, 라운드 종료 요약을 화면 문자열로 만든다.

        Args:
            없음.

        Returns:
            list: 라운드 결과 표시 문자열 목록.
        """

        if not self.round_summary:
            return []

        lines = [
            "라운드 %d 결과" % self.round_summary["hand_no"],
            "승자: %s" % self.round_summary["winner"],
            "팟: %d칩" % self.round_summary["pot"],
            "당신의 족보: %s" % self.round_summary["player_hand_name"],
            "%s의 족보: %s" % (self.bot.name, self.round_summary["bot_hand_name"]),
            "현재 칩 - 당신: %d / %s: %d" % (
                self.player.stack,
                self.bot.name,
                self.bot.stack,
            ),
        ]
        if self.latest_feedback:
            lines.append("전략 피드백: %s" % self.latest_feedback["short_term"])
        return lines
