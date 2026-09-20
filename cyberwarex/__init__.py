"""cyberwarex: one-line access to CyberWareX's x402 agent APIs.

Quick start (free trial, no wallet):

    from cyberwarex import CyberwareX
    cx = CyberwareX()                      # free_trial=True by default
    print(cx.search("x402 protocol"))
    print(cx.fetch("https://example.com"))

Paid, pay-per-call over x402 (needs `pip install cyberwarex[x402]`):

    cx = CyberwareX(free_trial=False, private_key="0x...")
    print(cx.token_safety("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"))

Framework tool factories:

    from cyberwarex import get_langchain_tools, get_crewai_tools
"""

from .client import (
    APIError,
    CyberwareX,
    CyberwareXError,
    PaymentRequiredError,
    RateLimitError,
    ServerError,
    SERVICES,
    X402NotInstalledError,
)

__version__ = "0.1.0"

__all__ = [
    "CyberwareX",
    "CyberwareXError",
    "PaymentRequiredError",
    "RateLimitError",
    "ServerError",
    "APIError",
    "X402NotInstalledError",
    "SERVICES",
    "get_langchain_tools",
    "get_crewai_tools",
    "__version__",
]


def get_langchain_tools(client=None):
    """Return CyberWareX tools as LangChain BaseTool objects.

    Lazily imports langchain_core, so importing cyberwarex never requires it.
    """
    from .langchain_tools import get_langchain_tools as _factory

    return _factory(client)


def get_crewai_tools(client=None):
    """Return CyberWareX tools as CrewAI BaseTool objects.

    Lazily imports crewai_tools, so importing cyberwarex never requires it.
    """
    from .crewai_tools import get_crewai_tools as _factory

    return _factory(client)
