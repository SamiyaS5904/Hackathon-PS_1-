"""Assistant cost: the assistant service records token use after each answer (as the user who asked);
the College Admin sees their college's cost, the platform owner every college's."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app import usage
from app.core.deps import Ctx, allow, org_ctx
from app.db.models import UserRow
from app.routers.platform import owner

router = APIRouter(tags=["usage"])


@router.post("/api/orgs/{org}/assistant/usage", status_code=204, response_class=Response)
def record_usage(body: usage.UsageIn, ctx: Ctx = Depends(org_ctx)) -> Response:
    usage.record(ctx.state.id, body)
    return Response(status_code=204)


@router.get("/api/orgs/{org}/assistant/usage", response_model=usage.UsageOut)
def get_usage(ctx: Ctx = Depends(org_ctx)) -> usage.UsageOut:
    allow("" if ctx.member.role == "admin" else "The assistant's cost is shown to the College Admin.")
    return usage.report(ctx.state.id)


@router.get("/api/platform/assistant-usage", response_model=dict[str, usage.Period])
def platform_usage(_: UserRow = Depends(owner)) -> dict[str, usage.Period]:
    return usage.all_colleges()
