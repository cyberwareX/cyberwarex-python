"""Offline unit tests for the cyberwarex client.

Run with:  python -m pytest

No network calls happen here: we inject a fake requests.Session so every
request is intercepted and answered locally.
"""

import json

import pytest

from cyberwarex import (
    CyberwareX,
    PaymentRequiredError,
    RateLimitError,
    ServerError,
    X402NotInstalledError,
)


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, content_type="application/json", content=b"", text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.headers = {"Content-Type": content_type}
        self.content = content
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


class FakeSession:
    """Records the last request and returns a queued response."""

    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "json": json,
                "headers": headers or {},
                "timeout": timeout,
            }
        )
        return self.response


def test_free_trial_header_is_set_by_default():
    resp = FakeResponse(status_code=200, json_data={"results": ["ok"]})
    fake = FakeSession(resp)
    cx = CyberwareX(session=fake)  # free_trial defaults to True

    out = cx.search("x402 protocol", max_results=3)

    assert out == {"results": ["ok"]}
    assert len(fake.calls) == 1
    call = fake.calls[0]
    # The free-trial header must be present and equal to "1".
    assert call["headers"].get("X-Free-Trial") == "1"
    # It hit the search service search endpoint with our query.
    assert call["url"] == "https://search.cyberwarex.com/search"
    assert call["params"]["q"] == "x402 protocol"
    assert call["params"]["max_results"] == 3
    # A timeout is always passed.
    assert call["timeout"] == cx.timeout


def test_free_trial_can_be_disabled():
    resp = FakeResponse(status_code=200, json_data={"ok": True})
    fake = FakeSession(resp)
    cx = CyberwareX(free_trial=False, session=fake)

    cx.fetch("https://example.com")

    assert "X-Free-Trial" not in fake.calls[0]["headers"]


def test_402_without_wallet_raises_payment_required():
    resp = FakeResponse(status_code=402, json_data={"error": "payment required"})
    fake = FakeSession(resp)
    cx = CyberwareX(session=fake)  # no wallet configured

    with pytest.raises(PaymentRequiredError) as exc_info:
        cx.token_safety("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")

    msg = str(exc_info.value)
    # The documented remedy must be spelled out for the user.
    assert "free trial" in msg.lower()
    assert "private_key" in msg
    assert "cyberwarex[x402]" in msg


def test_429_raises_rate_limit_error():
    resp = FakeResponse(status_code=429, json_data={"error": "slow down"})
    fake = FakeSession(resp)
    cx = CyberwareX(session=fake)

    with pytest.raises(RateLimitError):
        cx.chain_price("eth")


def test_5xx_raises_server_error():
    resp = FakeResponse(status_code=503, json_data={"error": "upstream down"})
    fake = FakeSession(resp)
    cx = CyberwareX(session=fake)

    with pytest.raises(ServerError):
        cx.search("anything")


def test_binary_endpoint_returns_bytes():
    png = b"\x89PNG\r\n\x1a\n" + b"fakepng"
    resp = FakeResponse(status_code=200, content_type="image/png", content=png)
    fake = FakeSession(resp)
    cx = CyberwareX(session=fake)

    out = cx.screenshot_url("https://example.com")

    assert isinstance(out, (bytes, bytearray))
    assert out == png


def test_paid_path_without_x402_package_raises_clear_error():
    # free_trial=False + wallet, but the x402/eth-account packages are absent in
    # the test venv, so building the paid session must raise a clear error.
    cx = CyberwareX(free_trial=False, private_key="0x" + "11" * 32)

    with pytest.raises(X402NotInstalledError) as exc_info:
        cx.token_safety("0x0000000000000000000000000000000000000000")

    msg = str(exc_info.value)
    assert "pip install" in msg


def test_has_wallet_flag():
    assert CyberwareX().has_wallet is False
    assert CyberwareX(private_key="0xabc").has_wallet is True


def test_json_result_shape_from_dict():
    resp = FakeResponse(status_code=200, json_data={"price_usd": 1.0})
    fake = FakeSession(resp)
    cx = CyberwareX(session=fake)

    out = cx.chain_price("usdc")
    assert isinstance(out, dict)
    assert json.dumps(out)  # serialisable
