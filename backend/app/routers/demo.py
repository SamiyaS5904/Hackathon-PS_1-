"""Public: the one-click logins of a demo college for the Demo page (demo accounts only, no real people)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.store import store

router = APIRouter(prefix="/api/demo", tags=["demo"])


class DemoLogin(BaseModel):
    role: str
    name: str
    email: str
    department: str | None = None
    section: str | None = None


class DemoCollege(BaseModel):
    id: str
    name: str
    sections: int
    students: int
    teachers: int
    rooms: int
    departments: list[dict]
    logins: list[DemoLogin]


@router.get("/{org}/logins", response_model=DemoCollege)
def demo_logins(org: str) -> DemoCollege:
    from app.seed import gndec

    state = store.org(org)
    if org != gndec.ORG_ID or state is None:  # only colleges built for showing; never a real college's people
        raise HTTPException(404, "Not found")
    c = state.college
    return DemoCollege(id=org, name=state.name, sections=len(c.sections), students=len(c.students),
                       teachers=len(c.teachers), rooms=len(c.venues),
                       departments=[{"id": d.id, "name": d.name} for d in c.departments],
                       logins=[DemoLogin(**x) for x in gndec.demo_logins(c)])
