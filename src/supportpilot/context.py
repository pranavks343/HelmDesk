"""Per-request runtime context (c25).

State is checkpointed and belongs to the *conversation*. Config (`configurable`) is per-call
plumbing (thread_id, checkpoint_id). Context is read-only *per-run* data that is not state and is
not checkpointed: who is asking, which model to use, which limits apply. Anything that must
survive a resume belongs in state, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from supportpilot import config


@dataclass(frozen=True)
class SupportContext:
    user_id: str
    plan_tier: Literal["free", "pro", "enterprise"] = "free"
    llm_provider: Literal["fake", "anthropic"] = field(
        default_factory=lambda: "anthropic" if config.default_provider() == "anthropic" else "fake"
    )
    model_name: str = field(default_factory=config.default_model)
    refund_auto_approve_limit: float = 20.0
    max_context_tokens: int = 1200
    summarize_after_messages: int = 12
    flaky_forum_failures: int = 1
    fake_behavior: Literal["normal", "tool_loop", "bad_answer"] = "normal"
