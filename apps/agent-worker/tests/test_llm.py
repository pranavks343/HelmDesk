from llm import FakeLLM, get_gateway


def test_fake_llm_classify_billing():
    result = FakeLLM().classify("I was charged twice, need a refund on my invoice", [])
    assert result.category == "billing"
    assert 0 <= result.confidence <= 1


def test_fake_llm_classify_technical():
    result = FakeLLM().classify("getting an error, the api is down", [])
    assert result.category == "technical"


def test_fake_llm_classify_defaults_to_general():
    result = FakeLLM().classify("hello there", [])
    assert result.category == "general"
    assert result.confidence < 0.7


def test_fake_llm_draft_reply_uses_top_kb_hit():
    from tools import kb_search

    hits = kb_search("sso setup")
    result = FakeLLM().draft_reply("how do I set up sso", [], hits)
    assert "SSO" in result.text or "SAML" in result.text
    assert result.confidence > 0


def test_fake_llm_draft_reply_no_hits_low_confidence():
    result = FakeLLM().draft_reply("something obscure", [], [])
    assert result.confidence < 0.5


def test_get_gateway_defaults_to_fake():
    gw = get_gateway("fake")
    assert isinstance(gw, FakeLLM)


def test_get_gateway_anthropic_requires_no_network_call_to_construct():
    gw = get_gateway("anthropic", api_key="sk-test-not-real", model="claude-sonnet-5")
    assert gw.__class__.__name__ == "AnthropicLLM"
