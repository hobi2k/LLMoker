"""Qwen-Agent가 포커 문맥을 조회할 때 쓰는 게임 전용 도구를 정의한다."""

import json
from copy import deepcopy

from qwen_agent.tools.base import BaseTool


_TOOL_CONTEXT = {}
_LAST_SELECTED_DIALOGUE_INDEX = None


def get_and_clear_selected_dialogue_index():
    """
    SelectDialogueLineTool이 마지막으로 선택한 인덱스를 가져오고 초기화한다.

    Returns:
        마지막 선택 인덱스 정수 또는 None이다.
    """

    global _LAST_SELECTED_DIALOGUE_INDEX
    idx = _LAST_SELECTED_DIALOGUE_INDEX
    _LAST_SELECTED_DIALOGUE_INDEX = None
    return idx


def set_tool_context(context):
    """
    현재 요청에서 도구가 읽을 문맥을 통째로 교체한다.
    도구 구현이 전역 상태 하나만 보게 해 각 호출부가 같은 사전 구조를 공유하도록 만든다.

    Args:
        context: 이번 요청에서 도구가 참조할 문맥 사전이다.
    """

    global _TOOL_CONTEXT
    _TOOL_CONTEXT = deepcopy(context or {})


def _items_to_text(items):
    """
    도구 응답에 넣을 목록을 짧은 줄바꿈 문자열로 바꾼다.

    Args:
        items: 문자열 목록 또는 사전 목록이다.

    Returns:
        모델이 읽기 쉬운 짧은 문자열이다.
    """

    lines = []
    for item in items or []:
        if isinstance(item, dict):
            text = item.get("text") or item.get("summary") or str(item)
        else:
            text = str(item)
        text = " ".join(text.split())
        if text:
            lines.append(text)
    return "\n".join(lines) if lines else "(없음)"


def clear_tool_context():
    """
    현재 요청이 끝난 뒤 공유 문맥을 완전히 비운다.
    이전 요청의 로그나 기억이 다음 요청으로 새지 않도록 매 호출 마지막에 반드시 실행한다.
    """

    global _TOOL_CONTEXT
    _TOOL_CONTEXT = {}


class GetPublicStateTool(BaseTool):
    """
    현재 공개 포커 상태와 허용 행동 요약을 돌려주는 Qwen-Agent 도구다.
    행동 선택, 카드 교체, 대사 생성 모두 이 도구를 첫 조회 지점으로 사용한다.
    """

    name = "get_public_state"
    description = "현재 공개 포커 상태, 허용 행동, 팟, 스택, 내 손패 요약을 조회한다."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def call(self, params, **kwargs):
        """
        현재 공개 상태 문자열을 돌려준다.

        Args:
            params: Qwen-Agent가 넘긴 JSON 인자다.
            **kwargs: Qwen-Agent 내부 부가 인자다.

        Returns:
            공개 상태 문자열 사전이다.
        """

        self._verify_json_format_args(params)
        return _TOOL_CONTEXT.get("public_state", "")


class GetMemoryTool(BaseTool):
    """
    최근 피드백 또는 장기 기억을 조회하는 Qwen-Agent 도구다.
    LLM이 직전 전략 초점과 장기 습관을 프롬프트 본문 대신 명시적으로 질의하게 만든다.
    """

    name = "get_memory"
    description = "NPC의 최근 전략 피드백 또는 장기 기억을 조회한다."
    parameters = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "description": "조회할 기억 범위",
                "enum": ["short_term", "long_term"],
            },
            "limit": {
                "type": "integer",
                "description": "가져올 최대 항목 수",
            },
        },
        "required": ["scope"],
    }

    def call(self, params, **kwargs):
        """
        요청한 범위의 기억 목록을 돌려준다.

        Args:
            params: Qwen-Agent가 넘긴 JSON 인자다.
            **kwargs: Qwen-Agent 내부 부가 인자다.

        Returns:
            기억 범위와 항목 목록을 담은 사전이다.
        """

        args = self._verify_json_format_args(params)
        scope = args["scope"]
        limit = args.get("limit")
        if scope == "long_term":
            items = _TOOL_CONTEXT.get("long_term_memory", [])
        else:
            items = _TOOL_CONTEXT.get("recent_feedback", [])
        if limit is None:
            return _items_to_text(items)
        return _items_to_text(items[: max(1, int(limit))])


class GetRecentLogTool(BaseTool):
    """
    최근 공개 진행 로그를 조회하는 Qwen-Agent 도구다.
    대사 생성과 행동 판단이 모두 같은 공개 로그를 읽도록 출처를 하나로 고정한다.
    """

    name = "get_recent_log"
    description = "최근 공개 진행 로그를 조회한다."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "가져올 최대 로그 수",
            },
        },
        "required": [],
    }

    def call(self, params, **kwargs):
        """
        최근 공개 로그를 제한 개수만큼 돌려준다.

        Args:
            params: Qwen-Agent가 넘긴 JSON 인자다.
            **kwargs: Qwen-Agent 내부 부가 인자다.

        Returns:
            최근 로그 목록 사전이다.
        """

        args = self._verify_json_format_args(params)
        limit = args.get("limit")
        logs = _TOOL_CONTEXT.get("recent_log", [])
        if limit is None:
            return _items_to_text(logs)
        return _items_to_text(logs[: max(1, int(limit))])


class GetRoundSummaryTool(BaseTool):
    """
    라운드 종료 후 결과 요약을 조회하는 Qwen-Agent 도구다.
    정책 회고 단계에서 승패, 팟, 족보, 스택 변화를 한 번에 읽기 위해 사용한다.
    """

    name = "get_round_summary"
    description = "라운드 종료 후 승패, 팟, 족보, 스택 변화 같은 결과 요약을 조회한다."
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def call(self, params, **kwargs):
        """
        라운드 결과 요약을 돌려준다.

        Args:
            params: Qwen-Agent가 넘긴 JSON 인자다.
            **kwargs: Qwen-Agent 내부 부가 인자다.

        Returns:
            라운드 요약 사전이다.
        """

        self._verify_json_format_args(params)
        return json.dumps(_TOOL_CONTEXT.get("round_summary", {}), ensure_ascii=False)


class SelectDialogueLineTool(BaseTool):
    """
    미리 작성된 대사 목록에서 현재 상황에 맞는 번호 하나를 선택하는 Qwen-Agent 도구다.
    LLM이 자유 생성 대신 번호 선택만 하도록 제한해 출력 품질을 보장한다.
    """

    name = "select_dialogue_line"
    description = "현재 상황에 가장 어울리는 대사 번호를 선택한다."
    parameters = {
        "type": "object",
        "properties": {
            "index": {
                "type": "integer",
                "description": "선택할 대사 번호 (0부터 시작)",
            },
        },
        "required": ["index"],
    }

    def call(self, params, **kwargs):
        """
        선택한 번호에 해당하는 대사 텍스트를 돌려준다.

        Args:
            params: Qwen-Agent가 넘긴 JSON 인자다.
            **kwargs: Qwen-Agent 내부 부가 인자다.

        Returns:
            선택된 대사 문자열이다.
        """

        global _LAST_SELECTED_DIALOGUE_INDEX
        args = self._verify_json_format_args(params)
        lines = _TOOL_CONTEXT.get("dialogue_lines", [])
        try:
            index = int(args.get("index", 0))
        except (TypeError, ValueError):
            index = 0
        if not lines:
            _LAST_SELECTED_DIALOGUE_INDEX = 0
            return ""
        index = max(0, min(index, len(lines) - 1))
        _LAST_SELECTED_DIALOGUE_INDEX = index
        return lines[index]


def build_poker_tools():
    """
    Qwen-Agent가 사용할 포커 전용 도구 인스턴스 목록을 새로 만든다.
    브리지 런타임 초기화 시 한 번 호출돼 에이전트에 등록될 도구 집합을 구성한다.

    Returns:
        포커 전용 도구 인스턴스 목록이다.
    """

    return [
        GetPublicStateTool(),
        GetMemoryTool(),
        GetRecentLogTool(),
        GetRoundSummaryTool(),
    ]


def build_dialogue_select_tools():
    """
    대사 선택 전용 도구 인스턴스 목록을 새로 만든다.
    SelectDialogueLineTool 하나만 포함해 LLM이 번호 선택에만 집중하게 한다.

    Returns:
        대사 선택 전용 도구 인스턴스 목록이다.
    """

    return [SelectDialogueLineTool()]
