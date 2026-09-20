# cyberwarex

One line of Python to give your AI agent real-world superpowers: web search, live
web access, onchain data, and DeFi safety checks. Every call is pay-per-use in
USDC over the [x402](https://cyberwarex.com) protocol. There is no account and no
API key. Out of the box the client uses a FREE trial (a few calls per day per IP),
so it works with no wallet at all.

Live machine catalog: https://cyberwarex.com/agents.json

## Install

```bash
pip install cyberwarex
```

Optional extras:

```bash
pip install "cyberwarex[langchain]"   # LangChain tool factory
pip install "cyberwarex[crewai]"      # CrewAI tool factory
pip install "cyberwarex[x402]"        # pay per call with a wallet
```

## 1. Plain client (free trial, no wallet)

```python
from cyberwarex import CyberwareX

cx = CyberwareX()  # free_trial=True by default

# Fresh web search
print(cx.search("x402 protocol", max_results=3))

# Read a live page as clean markdown
print(cx.fetch("https://example.com"))

# Onchain data
print(cx.chain_price("eth"))
print(cx.chain_wallet("0x058D0Cc5CC97e61e8A9f38D6d6365bce525921B2"))

# Is this token safe to trade? (grade A-F + tradeable flag)
print(cx.token_safety("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"))
```

When the daily free-trial quota runs out you get a clear `PaymentRequiredError`
telling you to add a wallet or wait for the reset.

## 2. LangChain agent

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from cyberwarex import get_langchain_tools

tools = get_langchain_tools()  # free trial by default; pass a client to configure
agent = create_react_agent(ChatOpenAI(model="gpt-4o-mini"), tools)

result = agent.invoke(
    {"messages": [("user", "Search the web for the latest on the x402 protocol.")]}
)
print(result["messages"][-1].content)
```

Each tool ships with a name, description, and a "when to use" hint pulled from the
CyberWareX catalog, so the model knows when to reach for it. CrewAI works the same
way via `from cyberwarex import get_crewai_tools`.

## 3. Paid, pay-per-call with a wallet

```python
from cyberwarex import CyberwareX

# Base wallet funded with a little USDC. Requires: pip install "cyberwarex[x402]"
cx = CyberwareX(free_trial=False, private_key="0xYOUR_PRIVATE_KEY")

# On an HTTP 402 the client signs the USDC authorization and retries for you.
report = cx.token_safety("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", chain="base")
print(report)
```

You can also keep `free_trial=True` together with a wallet: the client tries the
free trial first and only pays once the free quota is exhausted.

We never hand-roll the crypto. Paid calls detect and use the official `x402` pip
package to sign and settle. If it is not installed you get a clear error pointing
you to `pip install "cyberwarex[x402]"` or to the free trial.

## Services wrapped

| Method | Service | What it does |
| --- | --- | --- |
| `search`, `search_contents`, `page_contents`, `news` | search.cyberwarex.com | Web search and page reading |
| `fetch`, `extract`, `screenshot_url`, `pdf`, `ocr` | web.cyberwarex.com | Live web access, screenshots, PDF, OCR |
| `chain_price`, `chain_balance`, `chain_wallet`, `chain_token`, `chain_gas`, `chain_tx`, `chain_ens`, `chain_block`, `chain_erc20_balance` | chain.cyberwarex.com | Onchain data across EVM chains |
| `token_safety`, `honeypot_check`, `contract_risk`, `token_verdict` | oracle.cyberwarex.com | DeFi rug and honeypot safety |

## Errors

- `PaymentRequiredError` - HTTP 402 and no wallet configured (free quota used up).
- `RateLimitError` - HTTP 429, slow down and retry.
- `ServerError` - HTTP 5xx from an upstream service.
- `X402NotInstalledError` - a wallet was set but the `x402` package is missing.
- `CyberwareXError` - base class and network/timeout failures.

## Pricing

Pay-per-call in USDC on Base, settled over x402. No account, no API key, no
monthly fee. Prices per endpoint are published in the live catalog at
https://cyberwarex.com/agents.json (for example web search is 0.003 USDC per query
and a full token safety report is 0.06 USDC).

## License

MIT. Author: CyberWareX. Homepage: https://cyberwarex.com
