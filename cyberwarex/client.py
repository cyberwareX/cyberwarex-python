"""CyberwareX x402 client.

A tiny, dependency-light client for CyberWareX's x402-native agent APIs.

Out of the box it uses the FREE trial path (header ``X-Free-Trial: 1``), which
needs no wallet and only the ``requests`` package. A few calls per day per IP
are allowed on the free trial. When you supply a wallet private key, a 402
Payment Required response is settled automatically over the x402 protocol using
the optional ``x402`` pip package (we never hand-roll the crypto).
"""

from __future__ import annotations

import json as _json
from typing import Any, Dict, Optional

import requests

__all__ = [
    "CyberwareX",
    "CyberwareXError",
    "PaymentRequiredError",
    "RateLimitError",
    "ServerError",
    "APIError",
    "X402NotInstalledError",
    "SERVICES",
]

# Base URLs for the wrapped services (from https://cyberwarex.com/agents.json).
SERVICES = {
    "search": "https://search.cyberwarex.com",
    "web": "https://web.cyberwarex.com",
    "chain": "https://chain.cyberwarex.com",
    "oracle": "https://oracle.cyberwarex.com",
}

DEFAULT_TIMEOUT = 30.0
_FREE_TRIAL_HEADER = "X-Free-Trial"
_USER_AGENT = "cyberwarex-python/0.1.0 (+https://cyberwarex.com)"


class CyberwareXError(Exception):
    """Base class for all cyberwarex client errors."""


class PaymentRequiredError(CyberwareXError):
    """Raised on HTTP 402 when no wallet is configured to settle payment.

    The free trial pool is exhausted (or the endpoint has no free trial). Either
    pass a wallet ``private_key=`` to pay per call over x402, or wait for the
    daily free-trial quota to reset.
    """


class RateLimitError(CyberwareXError):
    """Raised on HTTP 429 (too many requests)."""


class ServerError(CyberwareXError):
    """Raised on HTTP 5xx (upstream service error)."""


class APIError(CyberwareXError):
    """Raised on other non-success HTTP responses (4xx that are not 402/429)."""


class X402NotInstalledError(CyberwareXError):
    """Raised when a wallet is configured but the x402 package is missing."""


def _extract_message(response: requests.Response) -> str:
    """Best-effort human-readable message from a response body."""
    try:
        data = response.json()
        if isinstance(data, dict):
            for key in ("error", "message", "detail", "reason"):
                if key in data and data[key]:
                    return str(data[key])
        return _json.dumps(data)[:400]
    except ValueError:
        text = (response.text or "").strip()
        return text[:400]


class CyberwareX:
    """Client for the CyberWareX x402 agent APIs.

    Args:
        free_trial: When True (default) requests carry the ``X-Free-Trial: 1``
            header so they work with no wallet, within the daily free quota.
        private_key: Optional hex private key ("0x...") of a Base wallet funded
            with USDC. When set, a 402 response is settled automatically via the
            x402 protocol and the call is retried. Requires ``pip install x402``.
        account: Optional pre-built eth-account ``LocalAccount``. Takes
            precedence over ``private_key`` if both are given.
        timeout: Per-request timeout in seconds (default 30).
        session: Optional ``requests.Session`` to reuse for the free-trial path.
        services: Optional override of base URLs, keyed like ``SERVICES``.
    """

    def __init__(
        self,
        free_trial: bool = True,
        private_key: Optional[str] = None,
        account: Any = None,
        timeout: float = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
        services: Optional[Dict[str, str]] = None,
    ) -> None:
        self.free_trial = free_trial
        self.timeout = timeout
        self._private_key = private_key
        self._account = account
        self._services = dict(SERVICES)
        if services:
            self._services.update(services)

        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", _USER_AGENT)
        self._session.headers.setdefault("Accept", "application/json")

        # Lazily built x402-capable session (only when a wallet is present).
        self._x402_session: Optional[requests.Session] = None

    # ---- capability helpers ------------------------------------------------

    @property
    def has_wallet(self) -> bool:
        """True if a wallet (private key or account) is configured."""
        return bool(self._private_key or self._account is not None)

    def _base(self, service: str) -> str:
        try:
            return self._services[service].rstrip("/")
        except KeyError:
            raise CyberwareXError("Unknown service: %r" % service)

    def _build_x402_session(self) -> requests.Session:
        """Build (and cache) a requests session that auto-settles x402 402s.

        We do NOT implement any crypto here. We detect the optional ``x402``
        package (Coinbase's reference client) and let it sign the USDC
        EIP-3009 authorization and retry. If it is not importable, we raise a
        clear, actionable error.
        """
        if self._x402_session is not None:
            return self._x402_session

        # Resolve the signing account.
        account = self._account
        if account is None:
            if not self._private_key:
                raise X402NotInstalledError(
                    "No wallet configured. Pass private_key=... to pay via x402, "
                    "or use free_trial=True."
                )
            try:
                from eth_account import Account  # type: ignore
            except ImportError as exc:
                raise X402NotInstalledError(
                    "Paid x402 calls need the 'eth-account' package. "
                    "Install it with: pip install 'cyberwarex[x402]'  "
                    "(or pip install x402 eth-account). "
                    "Alternatively use free_trial=True for the no-wallet trial."
                ) from exc
            account = Account.from_key(self._private_key)

        # Detect the x402 requests helper. Support a couple of known layouts.
        x402_requests = None
        try:
            from x402.clients.requests import x402_requests as _xr  # type: ignore

            x402_requests = _xr
        except ImportError:
            try:
                from x402_requests import x402_requests as _xr  # type: ignore

                x402_requests = _xr
            except ImportError:
                x402_requests = None

        if x402_requests is None:
            raise X402NotInstalledError(
                "Paid x402 calls need the 'x402' package. Install it with: "
                "pip install 'cyberwarex[x402]'  (or pip install x402). "
                "Alternatively use free_trial=True for the no-wallet trial."
            )

        session = x402_requests(account)
        # Carry our identifying headers onto the paid session too.
        try:
            session.headers.setdefault("User-Agent", _USER_AGENT)
        except Exception:
            pass
        self._x402_session = session
        return session

    # ---- core request ------------------------------------------------------

    def _request(
        self,
        method: str,
        service: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        raw: bool = False,
    ) -> Any:
        """Perform a request, handling the free-trial and paid x402 paths.

        Behaviour:
        - free_trial + no wallet: send with X-Free-Trial; on 402 raise
          PaymentRequiredError.
        - free_trial + wallet: try free trial first; on 402 retry paid via x402.
        - no free_trial + wallet: go straight to the paid x402 path.
        - no free_trial + no wallet: send plain; on 402 raise (no way to pay).
        """
        url = self._base(service) + path

        # Straight-to-paid when the caller opted out of the free trial.
        if not self.free_trial and self.has_wallet:
            return self._paid_request(method, url, params, json_body, raw)

        headers = {}
        if self.free_trial:
            headers[_FREE_TRIAL_HEADER] = "1"

        try:
            response = self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise CyberwareXError("Request to %s timed out after %ss" % (url, self.timeout)) from exc
        except requests.RequestException as exc:
            raise CyberwareXError("Network error calling %s: %s" % (url, exc)) from exc

        if response.status_code == 402:
            if self.has_wallet:
                # Free trial exhausted; settle over x402.
                return self._paid_request(method, url, params, json_body, raw)
            raise PaymentRequiredError(
                "HTTP 402 Payment Required from %s. The free trial quota is used "
                "up (a few calls/day per IP). Pass a wallet private_key=... to pay "
                "per call over x402 (pip install 'cyberwarex[x402]'), or wait for "
                "the daily quota to reset. Detail: %s" % (url, _extract_message(response))
            )

        return self._handle(response, url, raw)

    def _paid_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]],
        json_body: Optional[Any],
        raw: bool,
    ) -> Any:
        session = self._build_x402_session()
        try:
            response = session.request(
                method,
                url,
                params=params,
                json=json_body,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise CyberwareXError("Paid request to %s timed out after %ss" % (url, self.timeout)) from exc
        except requests.RequestException as exc:
            raise CyberwareXError("Network error on paid call to %s: %s" % (url, exc)) from exc
        return self._handle(response, url, raw)

    def _handle(self, response: requests.Response, url: str, raw: bool) -> Any:
        """Turn a response into parsed data or raise a typed error."""
        code = response.status_code
        if code == 402:
            raise PaymentRequiredError(
                "HTTP 402 Payment Required from %s even after payment attempt. "
                "Detail: %s" % (url, _extract_message(response))
            )
        if code == 429:
            raise RateLimitError(
                "HTTP 429 Too Many Requests from %s. Slow down and retry later. "
                "Detail: %s" % (url, _extract_message(response))
            )
        if 500 <= code < 600:
            raise ServerError(
                "HTTP %d server error from %s. Detail: %s" % (code, url, _extract_message(response))
            )
        if not (200 <= code < 300):
            raise APIError(
                "HTTP %d from %s. Detail: %s" % (code, url, _extract_message(response))
            )

        if raw:
            return response.content

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return response.json()
        if content_type.startswith("image/") or "application/pdf" in content_type or "octet-stream" in content_type:
            return response.content
        # Fall back to text; try JSON opportunistically.
        try:
            return response.json()
        except ValueError:
            return response.text

    # ---- Agent Search (search.cyberwarex.com) ------------------------------

    def search(self, q: str, category: str = "general", max_results: int = 5, lang: Optional[str] = None, **params: Any) -> Any:
        """Web search. Returns clean JSON results.

        Args:
            q: The query string.
            category: general | news | images.
            max_results: Up to 10.
            lang: Optional language hint (e.g. "en").
        """
        p: Dict[str, Any] = {"q": q, "category": category, "max_results": max_results}
        if lang:
            p["lang"] = lang
        p.update(params)
        return self._request("GET", "search", "/search", params=p)

    def search_contents(self, q: str, max_results: int = 5, **params: Any) -> Any:
        """Web search with the top result pages already extracted to text."""
        p: Dict[str, Any] = {"q": q, "max_results": max_results}
        p.update(params)
        return self._request("GET", "search", "/search-contents", params=p)

    def page_contents(self, url: str, max_chars: Optional[int] = None, **params: Any) -> Any:
        """Read one web page as clean markdown/text (via the search service)."""
        p: Dict[str, Any] = {"url": url}
        if max_chars is not None:
            p["max_chars"] = max_chars
        p.update(params)
        return self._request("GET", "search", "/contents", params=p)

    def news(self, topic: str, **params: Any) -> Any:
        """Ranked news brief for a topic."""
        p: Dict[str, Any] = {"q": topic}
        p.update(params)
        return self._request("GET", "search", "/news", params=p)

    def answer(self, q: str, **params: Any) -> Any:
        """Answer engine: one call searches, reads the top pages, and returns a concise cited answer.

        Returns {"query", "answer", "sources": [{"title", "url"}], ...}. Use this when you want a
        grounded answer to a question instead of a list of links.
        """
        p: Dict[str, Any] = {"q": q}
        p.update(params)
        return self._request("GET", "search", "/answer", params=p)

    # ---- Agent Web Access (web.cyberwarex.com) -----------------------------

    def fetch(self, url: str, format: str = "markdown", **params: Any) -> Any:
        """Render a page to markdown/text/html (JavaScript-aware)."""
        p: Dict[str, Any] = {"url": url, "format": format}
        p.update(params)
        return self._request("GET", "web", "/fetch", params=p)

    def extract(self, url: str, selector: str, **params: Any) -> Any:
        """Extract elements from a page by CSS selector."""
        p: Dict[str, Any] = {"url": url, "selector": selector}
        p.update(params)
        return self._request("GET", "web", "/extract", params=p)

    def screenshot_url(self, url: str, **params: Any) -> bytes:
        """Full-page PNG screenshot of a URL. Returns raw PNG bytes."""
        p: Dict[str, Any] = {"url": url}
        p.update(params)
        return self._request("GET", "web", "/screenshot", params=p, raw=True)

    def pdf(self, url: str, **params: Any) -> bytes:
        """Render a URL to PDF. Returns raw PDF bytes."""
        p: Dict[str, Any] = {"url": url}
        p.update(params)
        return self._request("GET", "web", "/pdf", params=p, raw=True)

    def ocr(self, url: str, **params: Any) -> Any:
        """OCR: extract text from an image URL."""
        p: Dict[str, Any] = {"url": url}
        p.update(params)
        return self._request("GET", "web", "/ocr", params=p)

    # ---- Onchain Query (chain.cyberwarex.com) ------------------------------

    def chain_price(self, query: str, **params: Any) -> Any:
        """Spot USD price for a ticker, CoinGecko id, or token address."""
        p: Dict[str, Any] = {"query": query}
        p.update(params)
        return self._request("GET", "chain", "/price", params=p)

    def chain_balance(self, address: str, chain: str = "base", **params: Any) -> Any:
        """Native ETH/POL balance of an address with USD value."""
        p: Dict[str, Any] = {"address": address, "chain": chain}
        p.update(params)
        return self._request("GET", "chain", "/balance", params=p)

    def chain_erc20_balance(self, address: str, token: Optional[str] = None, chain: str = "base", **params: Any) -> Any:
        """ERC-20 balance (USDC by default, or any token) with symbol/decimals."""
        p: Dict[str, Any] = {"address": address, "chain": chain}
        if token:
            p["token"] = token
        p.update(params)
        return self._request("GET", "chain", "/erc20-balance", params=p)

    def chain_wallet(self, address: str, chain: str = "base", **params: Any) -> Any:
        """Wallet snapshot: native + USDC balance, tx count, EOA-or-contract."""
        p: Dict[str, Any] = {"address": address, "chain": chain}
        p.update(params)
        return self._request("GET", "chain", "/wallet", params=p)

    def chain_token(self, address: str, chain: str = "base", **params: Any) -> Any:
        """ERC-20 profile: on-chain metadata plus live DEX price/liquidity."""
        p: Dict[str, Any] = {"address": address, "chain": chain}
        p.update(params)
        return self._request("GET", "chain", "/token", params=p)

    def chain_gas(self, chain: str = "base", **params: Any) -> Any:
        """Live gas market: base fee, priority-fee percentiles, USD cost."""
        p: Dict[str, Any] = {"chain": chain}
        p.update(params)
        return self._request("GET", "chain", "/gas", params=p)

    def chain_tx(self, hash: str, chain: str = "base", **params: Any) -> Any:
        """Transaction lookup and decode (including ERC-20 transfers)."""
        p: Dict[str, Any] = {"hash": hash, "chain": chain}
        p.update(params)
        return self._request("GET", "chain", "/tx", params=p)

    def chain_ens(self, query: str, **params: Any) -> Any:
        """ENS resolution both directions (name to address, address to name)."""
        p: Dict[str, Any] = {"query": query}
        p.update(params)
        return self._request("GET", "chain", "/ens", params=p)

    def chain_block(self, chain: str = "base", **params: Any) -> Any:
        """Latest block: number, timestamp, age, base fee, gas used/limit."""
        p: Dict[str, Any] = {"chain": chain}
        p.update(params)
        return self._request("GET", "chain", "/block", params=p)

    # ---- DeFi Safety Oracle (oracle.cyberwarex.com) ------------------------

    def token_safety(self, address: str, chain: str = "base", **params: Any) -> Any:
        """Full token safety report: honeypot sim + contract powers + cross-check.

        Returns a grade (A-F) and a tradeable flag. Call this before any swap or
        token approval.
        """
        p: Dict[str, Any] = {"address": address, "chain": chain}
        p.update(params)
        return self._request("GET", "oracle", "/token", params=p)

    def honeypot_check(self, address: str, chain: str = "base", **params: Any) -> Any:
        """Live buy/sell honeypot simulation for a token."""
        p: Dict[str, Any] = {"address": address, "chain": chain}
        p.update(params)
        return self._request("GET", "oracle", "/honeypot", params=p)

    def contract_risk(self, address: str, chain: str = "base", **params: Any) -> Any:
        """Contract powers and ownership analysis for a token."""
        p: Dict[str, Any] = {"address": address, "chain": chain}
        p.update(params)
        return self._request("GET", "oracle", "/contract", params=p)

    def token_verdict(self, address: str, chain: str = "base", **params: Any) -> Any:
        """One-call launch screening: GREEN/CAUTION/BLOCK plus reasons."""
        p: Dict[str, Any] = {"address": address, "chain": chain}
        p.update(params)
        return self._request("GET", "oracle", "/verdict", params=p)

    def __repr__(self) -> str:
        return "CyberwareX(free_trial=%r, has_wallet=%r)" % (self.free_trial, self.has_wallet)
