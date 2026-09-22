"""c28: swappable LLM. Mechanism: factory.get_gateway picks FakeGateway or AnthropicGateway from
SupportContext.llm_provider; the whole app runs offline by default; AnthropicGateway needs
langchain_anthropic to be importable, not a live call, to be exercised (skipped without a key)."""

import os

import pytest

from supportpilot.context import SupportContext
from supportpilot.llm.factory import get_gateway
from supportpilot.llm.fake import FakeGateway


def test_default_provider_is_fake():
    get_gateway.cache_clear()
    gw = get_gateway(SupportContext(user_id="u1"))
    assert isinstance(gw, FakeGateway)


def test_explicit_fake_provider():
    get_gateway.cache_clear()
    gw = get_gateway(SupportContext(user_id="u1", llm_provider="fake"))
    assert isinstance(gw, FakeGateway)


def test_anthropic_provider_constructs_without_a_live_call():
    get_gateway.cache_clear()
    from supportpilot.llm.anthropic import AnthropicGateway

    gw = get_gateway(SupportContext(user_id="u1", llm_provider="anthropic"))
    assert isinstance(gw, AnthropicGateway)


@pytest.mark.live
def test_anthropic_gateway_live_route():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    get_gateway.cache_clear()
    from langchain_core.messages import HumanMessage

    gw = get_gateway(SupportContext(user_id="u1", llm_provider="anthropic"))
    decision = gw.route([HumanMessage(content="how do I set up sso")], "", {})
    assert decision.next in {"kb_agent", "tech_agent", "billing_agent", "compose_reply", "fallback"}
