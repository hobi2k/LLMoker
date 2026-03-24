import sys
from dataclasses import dataclass, field

from backend.llm.agent import LocalLLMAgent
from backend.policy_loop import PolicyLoop
from backend.poker_hands import (
    card_image_path,
    compare_hands,
    create_deck,
    evaluate_hand,
    format_card_ko,
    format_cards_ko,
)
from backend.script_bot import SimpleScriptBot


PHASE_NAMES_KO = {
    "betting1": "첫 번째 베팅",
    "draw": "드로우",
    "betting2": "두 번째 베팅",
    "showdown": "쇼다운",
    "finished": "라운드 종료",
}


@dataclass
class PlayerState:
    """
    한 플레이어의 스택, 손패, 폴드 여부를 묶어 보관한다.
    포커 엔진 안에서는 플레이어와 봇 모두 같은 상태 구조를 써서, 베팅과 드로우 로직이 양쪽을 같은 코드 경로로 다룰 수 있게 한다.

    Args:
        name: 화면과 로그에 표시할 플레이어 이름이다.
        stack: 현재 보유 칩 수다.
        hand: 현재 손패다.
        folded: 이번 라운드에서 폴드했는지 여부다.

    """

    name: str
    stack: int
    hand: list = field(default_factory=list)
    folded: bool = False

class PokerMatch:
    """
    2인 5드로우 포커 매치의 상태기계와 라운드 진행을 관리한다.
    화면 코드는 이 클래스에 행동 적용과 상태 조회만 요청하고, 베팅 규칙·드로우·쇼다운·기억 저장은 모두 여기서 처리한다.

    Args:
        config: 게임 규칙과 LLM 실행 설정을 담은 백엔드 설정 객체다.
        memory_manager: LLM NPC 기억 저장소다.
        replay_logger: 라운드 결과 저장소다.
        player_name: 플레이어 표시 이름이다.
        bot_name: 상대 기본 표시 이름이다.

    """

    def __init__(self, config, memory_manager, replay_logger, player_name="플레이어", bot_name="스크립트봇"):
        self.config = config
        self.memory_manager = memory_manager
        self.replay_logger = replay_logger
        self.llm_agent = LocalLLMAgent(
            config.local_llm_path,
            config.llm_model_name,
            config.llm_runtime_python,
            config.llm_device,
            memory_manager,
        )
        self.policy_loop = PolicyLoop(memory_manager, self.llm_agent)
        self.player = PlayerState(player_name, config.starting_stack)
        self.bot = PlayerState(bot_name, config.starting_stack)
        self.script_bot = SimpleScriptBot()
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

    def _debug_terminal_log(self, message):
        """
        게임 화면에는 보이지 않는 디버그 정보를 터미널에 남긴다.
        LLM 판단 이유, 손패, 정책 회고처럼 플레이어에게 숨겨야 하는 정보는 모두 이 경로로만 기록한다.

        Args:
            message: 터미널에 찍을 디버그 문자열이다.

        """

        print("[LLMoker][DEBUG] %s" % message, file=sys.stderr, flush=True)

    def can_continue_match(self):
        """
        양쪽 모두 다음 라운드 앤티를 낼 수 있는지 확인한다.
        매치 종료 여부는 스택이 0인지가 아니라, 다음 라운드 앤티를 동시에 낼 수 있는지로 판단한다.

        Returns:
            다음 라운드를 시작할 수 있으면 `True`다.
        """

        return self.player.stack >= self.config.ante and self.bot.stack >= self.config.ante

    def to_snapshot(self):
        """
        현재 매치 상태를 저장소에 넣기 쉬운 사전으로 직렬화한다.
        Ren'Py 세이브 대신 이 스냅샷만 별도로 저장하므로, 화면 복원에 필요한 값들을 빠짐없이 평평한 자료형으로 담는다.

        Returns:
            세이브 복원에 필요한 매치 상태 사전이다.
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
            "llm_model_name": self.config.llm_model_name,
            "llm_device": self.config.llm_device,
            "memory_snapshot": self.memory_manager.export_character_memory(self.bot.name),
        }

    @classmethod
    def from_snapshot(cls, config, memory_manager, replay_logger, snapshot):
        """
        저장해 둔 스냅샷을 바탕으로 매치 객체를 다시 만든다.

        Args:
            config: 현재 세션의 백엔드 설정 객체다.
            memory_manager: 기억 저장소다.
            replay_logger: 리플레이 저장소다.
            snapshot: 이전에 직렬화해 둔 매치 상태 사전이다.

        Returns:
            스냅샷 상태를 복원한 `PokerMatch` 인스턴스다.
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
        match.config.llm_model_name = snapshot.get("llm_model_name", config.llm_model_name)
        match.config.llm_device = snapshot.get("llm_device", config.llm_device)
        match.memory_manager.replace_character_memory(
            match.bot.name,
            snapshot.get("memory_snapshot", {}),
        )
        match.llm_agent.reconfigure(
            llm_model_name=match.config.llm_model_name,
            llm_device=match.config.llm_device,
        )
        match._apply_bot_mode_name()
        return match

    def phase_name_ko(self):
        """
        현재 내부 페이즈 코드를 화면 표시용 한국어 이름으로 바꾼다.
        HUD와 종료 화면은 내부 enum 문자열 대신 이 함수를 통해 사용자가 읽기 쉬운 라벨을 받는다.

        Returns:
            현재 페이즈를 설명하는 한국어 문자열이다.
        """

        return PHASE_NAMES_KO.get(self.phase, self.phase)

    def _apply_bot_mode_name(self):
        """
        현재 상대 AI 모드에 맞춰 봇 표시 이름을 갱신한다.
        같은 매치 인스턴스를 유지한 채 모드만 바꿀 수 있으므로, 이름 갱신을 별도 함수로 분리해 스냅샷 복원과 모드 전환에서 함께 쓴다.
        """

        if self.bot_mode == "llm_npc":
            self.bot.name = "사야"
        else:
            self.bot.name = "스크립트봇"

    def set_bot_mode(self, bot_mode):
        """
        현재 매치에서 사용할 상대 AI 모드를 바꾸고 표시 이름도 맞춘다.
        설정 객체와 매치 객체가 서로 다른 값을 들고 가지 않도록 두 곳을 동시에 갱신한다.

        Args:
            bot_mode: 적용할 상대 AI 모드 문자열이다.

        """

        self.bot_mode = bot_mode
        self.config.bot_mode = bot_mode
        self._apply_bot_mode_name()

    def get_bot_mode_label(self):
        """
        현재 상대 AI 모드를 화면용 한국어 라벨로 돌려준다.
        UI에서는 내부 모드 문자열 대신 이 함수 결과만 사용해 화면 문구를 통일한다.

        Returns:
            현재 상대 AI 표시 문자열이다.
        """

        if self.bot_mode == "llm_npc":
            return "LLM NPC"
        return "스크립트봇"

    def get_llm_status_text(self):
        """
        현재 LLM 브리지 상태를 Ren'Py 화면에 안전하게 올릴 문자열로 바꾼다.
        중괄호는 Ren'Py 텍스트 태그로 오해될 수 있어 여기서 미리 이스케이프한다.

        Returns:
            중괄호를 이스케이프한 상태 문자열이다.
        """

        return self.llm_agent.last_status.replace("{", "{{").replace("}", "}}")

    def get_llm_runtime_label(self):
        """
        현재 LLM NPC 실행 방식을 화면에서 읽기 쉬운 라벨로 돌려준다.
        디버그용 내부 구현명을 노출하지 않고, UI에는 사람이 이해할 수 있는 한 줄 설명만 준다.

        Returns:
            LLM 실행 경로를 설명하는 문자열이다.
        """

        return "Transformers 런타임"

    def format_bot_hand_for_prompt(self):
        """
        봇 손패를 프롬프트에 바로 넣기 쉬운 한국어 카드 문자열 목록으로 바꾼다.
        프롬프트 빌더는 카드 포맷팅 규칙을 직접 알 필요 없이 이 함수 결과만 사용한다.

        Returns:
            봇 손패를 설명하는 문자열 목록이다.
        """

        return [format_card_ko(card) for card in self.bot.hand]

    def start_new_round(self):
        """
        새 라운드를 시작하면서 덱, 손패, 앤티, 로그, 베팅 상태를 초기화한다.
        양쪽 손패 배분, 앤티 차감, 공개 로그 시작 문장 작성까지 한 번에 처리해 라운드 시작 경로를 이 함수 하나로 고정한다.

        Returns:
            라운드 시작 직후 화면과 로그에 보여 줄 메시지 목록이다.
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
        if self.bot_mode == "llm_npc":
            self._debug_terminal_log(
                "라운드 %d 시작 / %s 시작 손패: %s (%s)" % (
                    self.hand_no,
                    self.bot.name,
                    format_cards_ko(self.bot.hand),
                    self.get_bot_hand_name(),
                )
            )
        self._start_betting_round("betting1")
        return list(self.action_log)

    def get_player_hand(self):
        """
        플레이어 손패를 원본을 건드리지 않도록 복사해서 돌려준다.
        화면 코드가 받은 목록을 수정해도 엔진 내부 상태가 깨지지 않게 사본만 반환한다.

        Returns:
            플레이어 손패 카드 목록 사본이다.
        """

        return list(self.player.hand)

    def get_bot_hand(self, reveal=False):
        """
        현재 상황에 따라 봇 손패를 공개하거나 뒷면 카드로 가려서 돌려준다.

        Args:
            reveal: 실제 손패를 그대로 보여 줄지 여부다.

        Returns:
            실제 봇 손패 또는 비공개 카드 자리표시 목록이다.
        """

        if reveal or self.round_over:
            return list(self.bot.hand)
        return [("Hidden", "Back")] * len(self.bot.hand)

    def get_player_hand_name(self):
        """
        플레이어 현재 손패의 족보 이름을 계산한다.
        HUD와 종료 화면이 같은 족보 계산 결과를 쓰도록 평가 함수를 한곳으로 감싼다.

        Returns:
            플레이어 족보의 한국어 이름이다.
        """

        return evaluate_hand(self.player.hand)[2]

    def get_bot_hand_name(self):
        """
        봇 현재 손패의 족보 이름을 계산한다.
        LLM 프롬프트, 디버그 로그, 종료 화면이 모두 같은 족보 계산 결과를 공유한다.

        Returns:
            봇 족보의 한국어 이름이다.
        """

        return evaluate_hand(self.bot.hand)[2]

    def is_match_finished(self):
        """
        라운드가 끝난 뒤 더 이상 다음 라운드를 열 수 없는지 확인한다.
        종료 화면에서 `다음 라운드` 버튼을 보여줄지 결정할 때 이 함수만 사용한다.

        Returns:
            매치가 최종 종료 상태면 `True`다.
        """

        return self.round_over and not self.can_continue_match()

    def get_round_result_title(self):
        """
        종료 화면 맨 위에 표시할 승패 제목을 만든다.
        내부 winner 값을 화면 친화적인 제목으로 바꿔 종료 레이아웃에서 그대로 쓸 수 있게 한다.

        Returns:
            라운드 종료 제목 문자열이다.
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
        """
        승자, 팟, 종료 방식에 맞춰 종료 화면 핵심 문구를 만든다.
        폴드 종료와 쇼다운 종료를 다른 문장으로 구분해 결과 맥락이 바로 읽히도록 만든다.

        Returns:
            종료 패널 본문에 들어갈 결과 문구다.
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
        """
        매치가 끝났는지, 아니면 다음 라운드로 이어지는지 설명한다.
        종료 원인이 플레이어 스택 부족인지, 봇 스택 부족인지, 일반 종료인지도 함께 문장에 반영한다.

        Returns:
            매치 지속 여부를 알려 주는 문자열이다.
        """

        if self.is_match_finished():
            if self.player.stack < self.config.ante:
                return "당신의 스택이 앤티보다 부족해 매치가 종료되었습니다."
            if self.bot.stack < self.config.ante:
                return "%s의 스택이 앤티보다 부족해 매치가 종료되었습니다." % self.bot.name
            return "더 이상 다음 라운드를 시작할 수 없어 매치가 종료되었습니다."
        return "다음 라운드를 계속 진행할 수 있습니다."

    def get_recent_log_text(self, limit=8):
        """
        최근 로그를 화면 텍스트 박스에 넣기 좋게 여러 줄 문자열로 합친다.
        로그 팝업은 이 문자열 하나만 받아 렌더링하므로 줄바꿈 처리도 여기서 끝낸다.

        Args:
            limit: 뒤에서부터 몇 줄을 묶을지 정한다.

        Returns:
            줄바꿈으로 연결한 최근 로그 문자열이다.
        """

        return "\n".join(self.action_log[-limit:])

    def get_public_log_lines(self, limit=8):
        """
        플레이어와 NPC 모두가 볼 수 있는 공개 로그만 잘라서 돌려준다.
        프롬프트에는 비공개 손패 정보 대신 이 공개 로그만 들어가도록 경계를 만든다.

        Args:
            limit: 뒤에서부터 몇 줄을 돌려줄지 정한다.

        Returns:
            공개 로그 문자열 목록이다.
        """

        return list(self.public_log[-limit:])

    def is_player_turn(self):
        """
        현재 상태에서 플레이어가 실제로 행동을 고를 차례인지 판정한다.
        화면 버튼 활성화 여부와 입력 처리 가능 여부가 모두 이 판정에 의존한다.

        Returns:
            플레이어 턴이면 `True`다.
        """

        return self.phase in ("betting1", "betting2") and self.current_actor == "player" and not self.round_over

    def get_player_amount_to_call(self):
        """
        플레이어가 현재 베팅을 맞추기 위해 더 내야 할 칩 수를 계산한다.
        HUD, 버튼 라벨, 행동 검증이 같은 콜 금액 계산을 공유하게 한다.

        Returns:
            플레이어 기준 콜 금액이다.
        """

        return max(0, self.current_bet - self.player_contribution)

    def get_bot_amount_to_call(self):
        """
        봇이 현재 베팅을 맞추기 위해 더 내야 할 칩 수를 계산한다.
        스크립트봇과 LLM NPC 모두 이 함수 결과를 기준으로 응답 행동을 결정한다.

        Returns:
            봇 기준 콜 금액이다.
        """

        return max(0, self.current_bet - self.bot_contribution)

    def get_player_available_actions(self):
        """
        현재 플레이어 턴에서 실제로 선택할 수 있는 합법 행동만 계산한다.
        턴이 아니면 빈 목록을 돌려줘 UI가 별도 방어 코드 없이도 버튼을 숨길 수 있게 한다.

        Returns:
            플레이어 행동 문자열 목록이다.
        """

        if not self.is_player_turn():
            return []
        return self._get_available_actions("player")

    def can_player_raise(self):
        """
        현재 플레이어 행동 목록 안에 레이즈가 포함되는지 확인한다.
        버튼 표시용 간단한 질의가 반복되므로 리스트 자체 대신 bool helper를 별도로 둔다.

        Returns:
            지금 레이즈가 가능하면 `True`다.
        """

        return "raise" in self.get_player_available_actions()

    def get_raise_total_amount(self):
        """
        플레이어가 이번 턴에 레이즈를 택할 때 실제로 내야 할 총액을 계산한다.
        현재 콜 금액 위에 고정 베팅 단위를 더한 값으로, 버튼 라벨과 설명 문구에서 함께 쓴다.

        Returns:
            현재 콜 금액과 고정 베팅액을 합친 총 납입액이다.
        """

        return self.get_player_amount_to_call() + self.config.fixed_bet

    def get_betting_status_text(self):
        """
        현재 베팅 상황을 HUD에 띄울 요약 문구로 만든다.
        체크 가능 상태와 콜 필요 상태를 다른 문장으로 나눠, 플레이어가 지금 판의 압박 정도를 바로 읽게 한다.

        Returns:
            콜 금액과 남은 레이즈 횟수를 담은 상태 문자열이다.
        """

        if self.phase not in ("betting1", "betting2"):
            return ""

        to_call = self.get_player_amount_to_call()
        raises_left = self.config.max_raises_per_round - self.raises_in_round
        if to_call > 0:
            return "현재 콜 금액: %d칩 / 남은 레이즈: %d회" % (to_call, max(0, raises_left))
        return "현재 체크 가능 / 남은 레이즈: %d회" % max(0, raises_left)

    def _start_betting_round(self, phase):
        """
        지정한 베팅 페이즈로 넘어가며 베팅 라운드 상태를 초기화한다.
        한 베팅 라운드가 끝날 때마다 기여 금액, 연속 체크 수, 레이즈 횟수를 모두 다시 시작점으로 돌린다.

        Args:
            phase: 시작할 베팅 페이즈 이름이다.

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
        """
        특정 주체 기준으로 지금 가능한 행동만 골라낸다.

        Args:
            actor_name: `player` 또는 `bot` 중 하나다.

        Returns:
            현재 상태에서 허용되는 행동 문자열 목록이다.
        """

        actor = self.player if actor_name == "player" else self.bot
        contribution = self.player_contribution if actor_name == "player" else self.bot_contribution
        to_call = max(0, self.current_bet - contribution)
        actions = ["fold"]

        if to_call == 0:
            actions.append("check")
            if actor.stack >= self.config.fixed_bet:
                actions.append("bet")
            return actions

        if actor.stack >= to_call:
            actions.append("call")
        if (
            actor.stack >= to_call + self.config.fixed_bet
            and self.raises_in_round < self.config.max_raises_per_round
        ):
            actions.append("raise")
        return actions

    def _deduct(self, actor, amount):
        """
        지정 플레이어 스택에서 칩을 빼고 팟에도 같은 금액을 더한다.
        칩 이동 규칙을 한곳으로 모아 베팅, 콜, 레이즈 모두 같은 회계 경로를 사용하게 한다.

        Args:
            actor: 칩을 낼 플레이어 상태 객체다.
            amount: 이번에 차감할 칩 수다.

        """

        actor.stack -= amount
        self.pot += amount

    def _finish_by_fold(self, winner):
        """
        폴드로 라운드가 끝났을 때 승자 정산과 종료 요약을 처리한다.
        팟 지급, 종료 상태 전환, 요약 생성, 디버그 로그 기록을 한 번에 끝내 다음 코드가 종료 조건을 다시 계산하지 않게 한다.

        Args:
            winner: 폴드 승리를 가져갈 플레이어 상태 객체다.

        """

        winner.stack += self.pot
        self.phase = "finished"
        self.round_over = True
        self._finalize_round_summary(winner_name=winner.name, folded=True)
        if self.bot_mode == "llm_npc":
            self._debug_terminal_log("폴드 종료 / 승자: %s / 팟: %d칩 / %s 손패: %s (%s)" % (
                winner.name,
                self.pot,
                self.bot.name,
                format_cards_ko(self.bot.hand),
                self.get_bot_hand_name(),
            ))

    def _advance_after_betting(self):
        """
        현재 베팅 라운드가 끝났을 때 다음 페이즈로 넘기거나 쇼다운을 연다.
        첫 베팅이 끝나면 드로우로, 두 번째 베팅이 끝나면 바로 쇼다운으로 넘긴다.

        Returns:
            다음 페이즈 전환 과정에서 화면에 보여 줄 메시지 목록이다.
        """

        if self.phase == "betting1":
            self.phase = "draw"
            if self.bot_mode == "llm_npc":
                self._debug_terminal_log("페이즈 전환 / 다음 페이즈: %s / 사유: 첫 번째 베팅 종료" % self.phase_name_ko())
            return ["드로우 단계로 넘어갑니다."]
        elif self.phase == "betting2":
            if self.bot_mode == "llm_npc":
                self._debug_terminal_log("페이즈 전환 / 다음 페이즈: 쇼다운 / 사유: 두 번째 베팅 종료")
            return self._resolve_showdown()
        return []

    def resolve_player_action(self, action):
        """
        플레이어가 선택한 베팅 행동을 적용하고 필요하면 봇 턴까지 이어서 진행한다.

        Args:
            action: 플레이어가 고른 행동 문자열이다.

        Returns:
            이번 입력으로 발생한 로그 메시지 목록이다.
        """

        if self.phase not in ("betting1", "betting2") or self.round_over or not self.is_player_turn():
            return ["지금은 그 행동을 할 수 없습니다."]
        available_actions = self._get_available_actions("player")
        if action not in available_actions:
            return ["지금은 그 행동을 선택할 수 없습니다."]

        if self.bot_mode == "llm_npc":
            self._debug_terminal_log(
                "플레이어 행동 선택 / 페이즈: %s / 선택: %s / 허용 행동: %s" % (
                    self.phase_name_ko(),
                    action,
                    ", ".join(available_actions),
                )
            )

        messages = self._apply_betting_action("player", action)
        if not self.round_over:
            if self.bot_mode == "llm_npc" and self.current_actor == "bot":
                self._debug_terminal_log("턴 전환 / 다음 차례: %s / 현재 페이즈: %s" % (self.bot.name, self.phase_name_ko()))
            messages.extend(self._run_bot_turns())
        return messages

    def _apply_betting_action(self, actor_name, action):
        """
        한 주체의 체크, 베팅, 콜, 레이즈, 폴드를 실제 상태에 반영한다.

        Args:
            actor_name: 행동 주체를 나타내는 `player` 또는 `bot`이다.
            action: 적용할 행동 문자열이다.

        Returns:
            행동 적용 중 발생한 로그 메시지 목록이다.
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
        """
        플레이어 턴이 돌아오거나 라운드가 끝날 때까지 봇 턴을 연속 처리한다.
        LLM NPC와 스크립트봇 모두 이 함수 안에서 행동을 선택하므로, 봇 턴 처리의 단일 진입점 역할을 한다.

        Returns:
            봇 턴 동안 누적된 로그 메시지 목록이다.
        """

        messages = []
        while not self.round_over and self.phase in ("betting1", "betting2") and self.current_actor == "bot":
            actions = self._get_available_actions("bot")
            if self.bot_mode == "llm_npc":
                self._debug_terminal_log(
                    "%s 행동 판단 시작 / 페이즈: %s / 손패: %s (%s) / 허용 행동: %s" % (
                        self.bot.name,
                        self.phase_name_ko(),
                        format_cards_ko(self.bot.hand),
                        self.get_bot_hand_name(),
                        ", ".join(actions),
                    )
                )
                llm_choice = self.llm_agent.choose_action(self, actions)
                if llm_choice.get("status") != "ok":
                    self.last_llm_reason = llm_choice.get("reason", "LLM 행동 선택 실패")
                    self._debug_terminal_log(
                        "%s 행동 선택 실패 / 이유: %s / 상태: %s" % (
                            self.bot.name,
                            self.last_llm_reason,
                            self.llm_agent.last_status,
                        )
                    )
                    raise RuntimeError("LLM NPC 행동 선택 실패: %s" % self.last_llm_reason)
                bot_action = llm_choice["action"]
                self.last_llm_reason = llm_choice.get("reason", "")
                self._debug_terminal_log(
                    "%s 행동 선택 완료 / 선택: %s / 이유: %s / 상태: %s" % (
                        self.bot.name,
                        bot_action,
                        self.last_llm_reason,
                        self.llm_agent.last_status,
                    )
                )
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
            if self.bot_mode == "llm_npc" and not self.round_over and self.current_actor == "player":
                self._debug_terminal_log("턴 전환 / 다음 차례: 플레이어 / 현재 페이즈: %s" % self.phase_name_ko())
        return messages

    def resolve_draw_phase(self, discard_indexes):
        """
        플레이어 교체 선택을 적용하고, 이어서 봇 교체까지 처리한다.

        Args:
            discard_indexes: 플레이어가 교체할 카드 인덱스 목록이다.

        Returns:
            드로우 단계에서 발생한 로그 메시지 목록이다.
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
            self._debug_terminal_log(
                "%s 카드 교체 판단 시작 / 현재 손패: %s (%s)" % (
                    self.bot.name,
                    format_cards_ko(self.bot.hand),
                    self.get_bot_hand_name(),
                )
            )
            draw_choice = self.llm_agent.choose_discards(self, self.config.max_discards)
            if draw_choice.get("status") != "ok":
                self._debug_terminal_log(
                    "%s 카드 교체 판단 실패 / 이유: %s / 상태: %s" % (
                        self.bot.name,
                        draw_choice.get("reason", "LLM 교체 판단 실패"),
                        self.llm_agent.last_status,
                    )
                )
                raise RuntimeError("LLM NPC 카드 교체 판단 실패: %s" % draw_choice.get("reason", "LLM 교체 판단 실패"))
            bot_discards = draw_choice["discard_indexes"]
            self._debug_terminal_log(
                "%s 카드 교체 선택 완료 / 버릴 인덱스: %s / 이유: %s / 상태: %s" % (
                    self.bot.name,
                    bot_discards,
                    draw_choice.get("reason", ""),
                    self.llm_agent.last_status,
                )
            )
        else:
            bot_discards = self.script_bot.choose_discards(self.bot.hand, self.config.max_discards)
        if bot_discards:
            self._replace_cards(self.bot, bot_discards)
            messages.append("%s은(는) %d장의 카드를 교체했습니다." % (self.bot.name, len(bot_discards)))
        else:
            messages.append("%s은(는) 교체 없이 진행했습니다." % self.bot.name)
        if self.bot_mode == "llm_npc":
            self._debug_terminal_log(
                "%s 드로우 후 손패: %s (%s)" % (
                    self.bot.name,
                    format_cards_ko(self.bot.hand),
                    self.get_bot_hand_name(),
                )
            )

        messages.append("당신의 현재 손패: %s" % format_cards_ko(self.player.hand))
        self.action_log.extend(messages)
        self.public_log.extend([line for line in messages if not line.startswith("당신의 현재 손패:")])
        self._start_betting_round("betting2")
        return messages

    def _replace_cards(self, actor, discard_indexes):
        """
        지정한 카드 인덱스만 새 카드로 바꿔 손패를 갱신한다.
        드로우 규칙 자체는 단순히 인덱스 자리에 새 카드를 넣는 형태라, 플레이어와 봇 모두 같은 함수로 처리한다.

        Args:
            actor: 카드를 교체할 플레이어 상태 객체다.
            discard_indexes: 교체할 손패 인덱스 목록이다.

        """

        for index in discard_indexes:
            actor.hand[index] = self.deck.pop()

    def _resolve_showdown(self):
        """
        양쪽 손패를 비교해 승자를 정하고 팟을 정산한다.
        공개 손패 로그, 승자 정산, LLM 디버그 로그를 모두 이 함수에서 끝내 쇼다운 흐름을 단일 경로로 유지한다.

        Returns:
            쇼다운 공개와 정산 과정에서 생긴 로그 메시지 목록이다.
        """

        result, player_rank, bot_rank = compare_hands(self.player.hand, self.bot.hand)
        self.phase = "showdown"
        messages = [
            "쇼다운입니다.",
            "당신의 손패: %s (%s)" % (format_cards_ko(self.player.hand), player_rank[2]),
            "%s의 손패: %s (%s)" % (self.bot.name, format_cards_ko(self.bot.hand), bot_rank[2]),
        ]
        if self.bot_mode == "llm_npc":
            self._debug_terminal_log(
                "쇼다운 / 플레이어: %s (%s) / %s: %s (%s)" % (
                    format_cards_ko(self.player.hand),
                    player_rank[2],
                    self.bot.name,
                    format_cards_ko(self.bot.hand),
                    bot_rank[2],
                )
            )

        if result == "player":
            self.player.stack += self.pot
            messages.append("당신이 이번 라운드를 가져갔습니다.")
            self.action_log.extend(messages)
            self._finalize_round_summary(self.player.name, folded=False)
            if self.bot_mode == "llm_npc":
                self._debug_terminal_log("쇼다운 결과 / 승자: %s / 팟: %d칩" % (self.player.name, self.pot))
        elif result == "bot":
            self.bot.stack += self.pot
            messages.append("%s이(가) 이번 라운드를 가져갔습니다." % self.bot.name)
            self.action_log.extend(messages)
            self._finalize_round_summary(self.bot.name, folded=False)
            if self.bot_mode == "llm_npc":
                self._debug_terminal_log("쇼다운 결과 / 승자: %s / 팟: %d칩" % (self.bot.name, self.pot))
        else:
            split = self.pot // 2
            self.player.stack += split
            self.bot.stack += self.pot - split
            messages.append("무승부입니다. 팟을 나눠 가집니다.")
            self.action_log.extend(messages)
            self._finalize_round_summary("무승부", folded=False)
            if self.bot_mode == "llm_npc":
                self._debug_terminal_log("쇼다운 결과 / 무승부 / 팟: %d칩" % self.pot)
        return messages

    def _finalize_round_summary(self, winner_name, folded):
        """
        라운드 종료 요약을 만들고 기억 저장과 리플레이 기록까지 마친다.
        승패 확정 뒤 해야 하는 부수 작업을 여기에 몰아, 쇼다운 종료와 폴드 종료가 같은 후처리 경로를 쓰게 한다.

        Args:
            winner_name: 이번 라운드 승자 이름이다.
            folded: 폴드 종료 여부다.

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
        self.latest_feedback = self.policy_loop.persist_feedback(
            self.round_summary,
            self.public_log,
            self.bot_mode,
        )
        if self.bot_mode == "llm_npc" and self.latest_feedback:
            feedback_status = self.latest_feedback.get("status", "ok")
            self._debug_terminal_log(
                "%s 정책 피드백 %s / 단기: %s / 장기: %s / 초점: %s" % (
                    self.bot.name,
                    "실패" if feedback_status == "error" else "완료",
                    self.latest_feedback.get("short_term", ""),
                    self.latest_feedback.get("long_term", ""),
                    self.latest_feedback.get("strategy_focus", ""),
                )
            )
        self.replay_logger.append_round(self.round_summary)

    def get_round_summary_lines(self):
        """
        라운드 종료 결과를 로그나 팝업에 넣기 쉬운 문자열 목록으로 만든다.
        종료 화면, 로그 팝업, 디버그 출력이 같은 요약 문장을 재사용할 수 있게 줄 단위 목록으로 반환한다.

        Returns:
            종료 화면에 쓸 요약 문자열 목록이다.
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
            if self.latest_feedback.get("strategy_focus"):
                lines.append("다음 전략 초점: %s" % self.latest_feedback["strategy_focus"])
        return lines
