"""Qwen-Agent가 포커 문맥을 조회할 때 쓰는 게임 전용 도구를 정의한다."""

from copy import deepcopy

from qwen_agent.tools.base import BaseTool


_TOOL_CONTEXT = {}


def set_tool_context(context):
    """
    현재 요청에서 도구가 읽을 문맥을 교체한다.

    Args:
        context: 이번 요청에서 도구가 참조할 문맥 사전이다.

    Returns:
        없음.
    """

    global _TOOL_CONTEXT
    _TOOL_CONTEXT = deepcopy(context or {})


def clear_tool_context():
    """
    현재 요청이 끝난 뒤 공유 문맥을 비운다.

    Args:
        없음.

    Returns:
        없음.
    """

    global _TOOL_CONTEXT
    _TOOL_CONTEXT = {}


class GetPublicStateTool(BaseTool):
    """
    현재 공개 포커 상태와 허용 행동 요약을 돌려준다.

    Args:
        없음.

    Returns:
        없음.
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
        return {"public_state": _TOOL_CONTEXT.get("public_state", "")}


class GetMemoryTool(BaseTool):
    """
    최근 피드백 또는 장기 기억을 조회한다.

    Args:
        없음.

    Returns:
        없음.
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
        limit = max(1, int(args.get("limit", 5)))
        if scope == "long_term":
            items = _TOOL_CONTEXT.get("long_term_memory", [])
        else:
            items = _TOOL_CONTEXT.get("recent_feedback", [])
        return {
            "scope": scope,
            "items": items[:limit],
        }


class GetRecentLogTool(BaseTool):
    """
    최근 공개 진행 로그를 조회한다.

    Args:
        없음.

    Returns:
        없음.
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
        limit = max(1, int(args.get("limit", 8)))
        return {
            "items": _TOOL_CONTEXT.get("recent_log", [])[:limit],
        }


class GetRoundSummaryTool(BaseTool):
    """
    라운드 종료 후 결과 요약을 조회한다.

    Args:
        없음.

    Returns:
        없음.
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
        return {"round_summary": _TOOL_CONTEXT.get("round_summary", {})}


def build_poker_tools():
    """
    Qwen-Agent가 쓸 포커 전용 도구 목록을 만든다.

    Args:
        없음.

    Returns:
        포커 전용 도구 인스턴스 목록이다.
    """

    return [
        GetPublicStateTool(),
        GetMemoryTool(),
        GetRecentLogTool(),
        GetRoundSummaryTool(),
    ]
