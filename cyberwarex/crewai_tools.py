"""CrewAI tool factory for CyberWareX x402 APIs.

Usage:

    from cyberwarex import get_crewai_tools
    tools = get_crewai_tools()             # free trial, no wallet

crewai (crewai-tools) is imported lazily inside the factory so that importing
cyberwarex never requires CrewAI to be installed.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

from ._toolspec import TOOL_SPECS
from .client import CyberwareX


def _result_to_text(result: Any) -> str:
    """Render a client result as a string suitable for an LLM tool return."""
    if isinstance(result, (bytes, bytearray)):
        return "<binary content: %d bytes>" % len(result)
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(result)


def get_crewai_tools(client: Optional[CyberwareX] = None) -> List[Any]:
    """Return the CyberWareX tools as CrewAI BaseTool instances.

    Args:
        client: An existing CyberwareX client. If None, a default free-trial
            client is created.

    Returns:
        A list of CrewAI BaseTool objects.

    Raises:
        ImportError: If crewai (crewai-tools) is not installed. Install it with
            ``pip install 'cyberwarex[crewai]'``.
    """
    try:
        # crewai-tools re-exports BaseTool; crewai.tools also provides it.
        try:
            from crewai.tools import BaseTool  # type: ignore
        except ImportError:
            from crewai_tools import BaseTool  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only without crewai
        raise ImportError(
            "get_crewai_tools requires crewai / crewai-tools. Install it with: "
            "pip install 'cyberwarex[crewai]'"
        ) from exc

    cx = client or CyberwareX()
    tools: List[Any] = []

    for name, spec in TOOL_SPECS.items():
        method = getattr(cx, spec["method"])
        arg_lines = "\n".join(
            "  - %s: %s" % (arg, desc) for arg, desc in spec.get("args", {}).items()
        )
        description = "%s\n\nWhen to use: %s\n\nArguments:\n%s" % (
            spec["description"],
            spec["use_when"],
            arg_lines,
        )

        def _make_run(bound_method):
            def _run(self, **kwargs: Any) -> str:
                return _result_to_text(bound_method(**kwargs))

            return _run

        tool_cls = type(
            "CyberwareXTool_%s" % name,
            (BaseTool,),
            {
                "name": name,
                "description": description,
                "_run": _make_run(method),
            },
        )
        tools.append(tool_cls())

    return tools
