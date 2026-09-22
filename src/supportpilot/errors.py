"""Exception types shared across the project."""

from __future__ import annotations


class TransientSourceError(Exception):
    """A flaky knowledge source failed; safe to retry (c8)."""


class TransientLLMError(Exception):
    """A transient LLM/API failure (rate limit, overloaded, timeout); safe to retry (c8)."""


class SimulatedCrash(RuntimeError):
    """Raised on purpose by the crash-injection hook to demo resume (c5/c19)."""
