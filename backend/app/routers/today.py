"""Staff home ("Today") and the setup checklist."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException

from app import today
from app.core.deps import Ctx, allow, org_ctx

router = APIRouter(prefix="/api/orgs/{org}", tags=["today"])


@router.get("/today", response_model=today.TodayReport)
def get_today(date: str | None = None, ctx: Ctx = Depends(org_ctx)) -> today.TodayReport:
    """Teachers away, classes that won't happen, moved classes, latest changes. Coordinators: own department."""
    allow("" if ctx.member.role in ("admin", "coordinator") else "The Today overview is for the College Admin and "
                                                                    "Department Coordinators.")
    d = date or today.now_date()
    try:
        datetime.date.fromisoformat(d)
    except ValueError:
        raise HTTPException(422, "Use a date like 2026-10-21") from None
    dept = ctx.member.department_id if ctx.member.role == "coordinator" else None
    return today.today_report(ctx.state, d, dept)


@router.get("/setup-status", response_model=today.SetupStatus)
def get_setup_status(ctx: Ctx = Depends(org_ctx)) -> today.SetupStatus:
    allow("" if ctx.member.role in ("admin", "coordinator") else "The setup checklist is for staff.")
    return today.setup_status(ctx.state)
