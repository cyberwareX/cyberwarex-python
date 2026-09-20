"""Static tool descriptions shared by the LangChain and CrewAI factories.

Each entry maps a tool name to a client method plus agent-facing text. The
descriptions and "use_when" hints are lifted from https://cyberwarex.com/agents.json
so an LLM knows when to reach for each tool. Plain hyphens only.
"""

# name -> dict(method, description, use_when, args)
TOOL_SPECS = {
    "cyberwarex_search": {
        "method": "search",
        "description": (
            "Search the open web and get clean JSON results back. Keyless, no "
            "search account needed."
        ),
        "use_when": (
            "Use whenever your agent needs fresh facts from the open web - one "
            "query, clean JSON back."
        ),
        "args": {
            "q": "The search query string.",
        },
    },
    "cyberwarex_web_fetch": {
        "method": "fetch",
        "description": (
            "Fetch a live web page and return it as clean, LLM-ready markdown. "
            "Renders JavaScript, so it works on modern sites."
        ),
        "use_when": (
            "Use when your agent must read a page it was handed or scrape live "
            "data - any time the answer lives on a website the model cannot see."
        ),
        "args": {
            "url": "The absolute URL of the page to fetch.",
        },
    },
    "cyberwarex_web_extract": {
        "method": "extract",
        "description": (
            "Extract specific elements from a web page by CSS selector and "
            "return their text/content."
        ),
        "use_when": (
            "Use when you need targeted data from a page (prices, tables, links) "
            "rather than the whole document."
        ),
        "args": {
            "url": "The absolute URL of the page.",
            "selector": "A CSS selector, for example 'h1' or '.price'.",
        },
    },
    "cyberwarex_chain_price": {
        "method": "chain_price",
        "description": (
            "Get the spot USD price for a crypto ticker, CoinGecko id, or token "
            "contract address."
        ),
        "use_when": (
            "Use when you need a live token or coin price without running a node "
            "or holding an API key."
        ),
        "args": {
            "query": "A ticker (eth), a CoinGecko id, or a token address.",
        },
    },
    "cyberwarex_wallet": {
        "method": "chain_wallet",
        "description": (
            "Get a wallet snapshot on an EVM chain: native + USDC balance, tx "
            "count, contract-or-EOA, and USD values."
        ),
        "use_when": (
            "Use when you need to inspect any wallet address balance or activity "
            "on Base and other EVM chains."
        ),
        "args": {
            "address": "The 0x wallet address to inspect.",
            "chain": "Chain name (default 'base').",
        },
    },
    "cyberwarex_token_safety": {
        "method": "token_safety",
        "description": (
            "Full DeFi safety report for a token: honeypot buy/sell simulation, "
            "contract powers, and a GoPlus cross-check. Returns a grade A-F and a "
            "tradeable flag."
        ),
        "use_when": (
            "Call before any swap, token approval, or 'should I buy this' "
            "decision - it catches honeypots and hidden sell-taxes so your agent "
            "never buys a coin it cannot sell."
        ),
        "args": {
            "address": "The 0x token contract address.",
            "chain": "Chain name (default 'base').",
        },
    },
}
