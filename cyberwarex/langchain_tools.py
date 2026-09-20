"""LangChain tool factory for CyberWareX x402 APIs.

Usage:

    from cyberwarex import get_langchain_tools
    tools = get_langchain_tools()          # free trial, no wallet
    # tools -> list[langchain_core.tools.BaseTool]

langchain_core is imported lazily inside the factory so that importing
cyberwarex never requires LangChain to be installed.
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


def get_langchain_tools(client: Optional[CyberwareX] = None) -> List[Any]:
    """Return the CyberWareX tools as LangChain BaseTool instances.

    Args:
        client: An existing CyberwareX client. If None, a default free-trial
            client is created.

    Returns:
        A list of langchain_core.tools.BaseTool objects.

    Raises:
        ImportError: If langchain-core is not installed. Install it with
            ``pip install 'cyberwarex[langchain]'``.
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:  # pragma: no cover - exercised only without langchain
        raise ImportError(
            "get_langchain_tools requires langchain-core. Install it with: "
            "pip install 'cyberwarex[langchain]'"
        ) from exc

    cx = client or CyberwareX()
    tools: List[Any] = []

    for name, spec in TOOL_SPECS.items():
        method_name = spec["method"]
        method = getattr(cx, method_name)
        arg_lines = "\n".join(
            "  - %s: %s" % (arg, desc) for arg, desc in spec.get("args", {}).items()
        )
        description = "%s\n\nWhen to use: %s\n\nArguments:\n%s" % (
            spec["description"],
            spec["use_when"],
            arg_lines,
        )

        def _make_func(bound_method):
            def _run(**kwargs: Any) -> str:
                return _result_to_text(bound_method(**kwargs))

            return _run

        tool = StructuredTool.from_function(
            func=_make_func(method),
            name=name,
            description=description,
        )
        tools.append(tool)

    return tools
