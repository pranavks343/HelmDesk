from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from supportpilot.tools.crm import load_crm


@tool
def get_error_code_doc(code: str) -> dict[str, Any]:
    """Explain a Nimbus error code such as E105 and how to fix it."""
    doc = load_crm()["error_codes"].get(code.upper())
    if doc is None:
        return {"code": code, "error": "unknown error code"}
    return {"code": code.upper(), **doc}
