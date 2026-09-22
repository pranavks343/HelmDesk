"""Picks a gateway implementation from context/env so the rest of the code never knows which
model runs (c28)."""

from __future__ import annotations

from functools import lru_cache

from supportpilot.context import SupportContext
from supportpilot.llm.fake import FakeGateway
from supportpilot.llm.gateway import LLMGateway


@lru_cache(maxsize=64)
def _build(ctx: SupportContext) -> LLMGateway:
    if ctx.llm_provider == "anthropic":
        from supportpilot.llm.anthropic import AnthropicGateway

        return AnthropicGateway(ctx.model_name)
    return FakeGateway(fake_behavior=ctx.fake_behavior)


def get_gateway(ctx: SupportContext) -> LLMGateway:
    """Cached by context value (``SupportContext`` is frozen/hashable) so a single graph run
    reuses one gateway instance - this is what lets ``FakeGateway`` track "first call" behaviour
    (bad_answer, tool_loop) across nodes within a run. Call ``get_gateway.cache_clear()`` (or use
    a context with a different ``user_id``) to isolate tests."""
    return _build(ctx)


get_gateway.cache_clear = _build.cache_clear  # type: ignore[attr-defined]
