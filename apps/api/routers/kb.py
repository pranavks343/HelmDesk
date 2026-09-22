from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core.kb_search import search
from core.security import CurrentUser

router = APIRouter(prefix="/kb", tags=["kb"])


class KBHitOut(BaseModel):
    doc_id: str
    title: str
    snippet: str
    score: float


@router.get("/search", response_model=list[KBHitOut])
async def kb_search(user: CurrentUser, q: str = Query(min_length=1)) -> list[KBHitOut]:
    hits = search(q)
    return [KBHitOut(doc_id=h.doc_id, title=h.title, snippet=h.snippet, score=h.score) for h in hits]
