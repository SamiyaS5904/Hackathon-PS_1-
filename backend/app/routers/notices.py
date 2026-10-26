"""Notices on Home (see app/notices.py): Coordinators post to their department, the College Admin to anyone."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app import notices
from app.core.deps import Ctx, org_ctx
from app.notices import NoticeOut
from app.notify import send

router = APIRouter(prefix="/api/orgs/{org}/notices", tags=["notices"])


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


class NoticeIn(BaseModel):
    title: str = Field(max_length=160)
    body: str = Field(default="", max_length=1000)
    kind: str
    department_id: str | None = None
    year: int | None = None
    section_id: str | None = None
    expires: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class NoticeResult(BaseModel):
    message: str
    notice: NoticeOut


@router.get("", response_model=list[NoticeOut])
def list_notices(ctx: Ctx = Depends(org_ctx)) -> list[NoticeOut]:
    return notices.visible(ctx.state.id, ctx.member, _today())


@router.post("", response_model=NoticeResult, status_code=201)
def post_notice(body: NoticeIn, ctx: Ctx = Depends(org_ctx)) -> NoticeResult:
    m = ctx.member
    dept = body.department_id or (m.department_id if m.role == "coordinator" else None)
    n, msg = notices.post(ctx.state.college, ctx.state.id, m, body.title, body.body, body.kind, dept, body.year,
                          body.section_id, body.expires, _today())
    if n is None:
        raise HTTPException(403 if msg == notices.can_post(m, body.kind, dept) else 422, msg)
    send(ctx.state.id, f"Notice: {n.title}", (n.body or f"From {m.name}")[:900], n.audience, m.user_id, link="/")
    return NoticeResult(message=msg, notice=NoticeOut(**n.model_dump(), can_delete=True))


@router.delete("/{notice_id}", status_code=204, response_class=Response)
def delete_notice(notice_id: str, ctx: Ctx = Depends(org_ctx)) -> Response:
    if notices.remove(ctx.state.id, ctx.member, notice_id) is None:
        raise HTTPException(404, "Notice not found.")
    return Response(status_code=204)
