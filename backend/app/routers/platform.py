"""Platform owner (Super Admin) endpoints. Anyone else gets 404, as if the page didn't exist."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import platform
from app.core.deps import current_user
from app.db.models import UserRow
from app.store import store

router = APIRouter(prefix="/api/platform", tags=["platform"])


def owner(user: UserRow = Depends(current_user)) -> UserRow:
    if not platform.is_owner(user):
        raise HTTPException(404, "Not found.")
    return user


class CollegeUpdate(BaseModel):
    plan: str | None = None
    status: str | None = None
    note: str | None = Field(default=None, max_length=500)


@router.get("/overview", response_model=platform.PlatformOverview)
def overview(_: UserRow = Depends(owner)) -> platform.PlatformOverview:
    return platform.overview()


@router.patch("/colleges/{org}", response_model=platform.CollegeSummary)
def update_college(org: str, body: CollegeUpdate, user: UserRow = Depends(owner)) -> platform.CollegeSummary:
    """Plan label, pause / read-only, a private note. Never the college's own data."""
    st = store.org(org)
    if st is None:
        raise HTTPException(404, "College not found.")
    if body.plan is not None and body.plan not in platform.PLANS:
        raise HTTPException(422, f"Plan must be one of: {', '.join(platform.PLANS)}.")
    if body.status is not None and body.status not in platform.STATUSES:
        raise HTTPException(422, f"Status must be one of: {', '.join(platform.STATUSES)}.")
    if body.status and body.status != "active" and st.is_demo:
        raise HTTPException(422, "The demo college stays open for everyone.")
    platform.update(org, user.name, plan=body.plan, status=body.status, note=body.note)
    accounts = platform._accounts()
    return platform.summarize(st, accounts.get(org, 0))
