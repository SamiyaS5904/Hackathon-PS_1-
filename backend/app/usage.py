"""The assistant's cost per college: token use recorded by the assistant service after every answer,
priced at Claude Opus 5.5 rates (USD per million tokens; change with the ASSISTANT_PRICE_* settings)."""

from __future__ import annotations

import os
import time
from datetime import date, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.db.models import AssistantUsageRow, SessionLocal

KEYS = ("requests", "input", "output", "cache_write", "cache_read")
PRICE = {  # USD per million tokens (Claude Opus 5.5)
    "input": float(os.environ.get("ASSISTANT_PRICE_INPUT", "4")),
    "output": float(os.environ.get("ASSISTANT_PRICE_OUTPUT", "20")),
    "cache_write": float(os.environ.get("ASSISTANT_PRICE_CACHE_WRITE", "5")),
    "cache_read": float(os.environ.get("ASSISTANT_PRICE_CACHE_READ", "0.2")),
}
USD_TO_INR = float(os.environ.get("USD_TO_INR", "84"))


class UsageIn(BaseModel):
    usd_micro: int | None = Field(default=None, ge=0, le=50_000_000)  # cost already priced by the assistant
    input: int = Field(default=0, ge=0, le=5_000_000)
    output: int = Field(default=0, ge=0, le=1_000_000)
    cache_write: int = Field(default=0, ge=0, le=5_000_000)
    cache_read: int = Field(default=0, ge=0, le=50_000_000)


class Period(BaseModel):
    requests: int = 0
    tokens: int = 0
    usd: float = 0.0
    inr: float = 0.0


class UsageOut(BaseModel):
    today: Period
    week: Period  # last 7 days
    month: Period  # this calendar month
    per_answer_inr: float  # average cost of one answer this month
    by_day: list[dict]  # last 14 days: {day, requests, usd}
    prices: dict[str, float]


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def record(org: str, u: UsageIn, day: str | None = None) -> None:
    day = day or _today()
    with SessionLocal() as db:
        row = db.get(AssistantUsageRow, (org, day))
        data = dict(row.data) if row else dict.fromkeys(KEYS, 0)
        data["requests"] = data.get("requests", 0) + 1
        before = _usd(data)  # cost so far, before this answer's tokens are added
        for k in ("input", "output", "cache_write", "cache_read"):
            data[k] = data.get(k, 0) + getattr(u, k)
        # Each answer's cost at its own model's price (the assistant mixes faster and stronger models).
        data["usd"] = before + (u.usd_micro / 1_000_000 if u.usd_micro is not None else _usd_tokens(u.model_dump()))
        if row is None:
            db.add(AssistantUsageRow(org_id=org, day=day, data=data))
        else:
            row.data = data
        db.commit()


def _usd_tokens(d: dict) -> float:
    return sum(d.get(k, 0) * PRICE[k] for k in PRICE) / 1_000_000


def _usd(d: dict) -> float:
    """A day's cost: the priced running total, or (older rows) its tokens at the strong model's price."""
    return d["usd"] if "usd" in d else _usd_tokens(d)


def _period(rows: list[AssistantUsageRow]) -> Period:
    req = sum(r.data.get("requests", 0) for r in rows)
    tokens = sum(r.data.get(k, 0) for r in rows for k in ("input", "output", "cache_write", "cache_read"))
    usd = sum(_usd(r.data) for r in rows)
    return Period(requests=req, tokens=tokens, usd=round(usd, 4), inr=round(usd * USD_TO_INR, 2))


def report(org: str) -> UsageOut:
    today = date.fromisoformat(_today())
    with SessionLocal() as db:
        rows = db.scalars(select(AssistantUsageRow).where(AssistantUsageRow.org_id == org)).all()
    week_start = (today - timedelta(days=6)).isoformat()
    month = today.isoformat()[:7]
    m = _period([r for r in rows if r.day[:7] == month])
    by_day = []
    for i in range(13, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        r = next((x for x in rows if x.day == d), None)
        by_day.append({"day": d, "requests": r.data.get("requests", 0) if r else 0,
                       "usd": round(_usd(r.data), 4) if r else 0.0})
    return UsageOut(today=_period([r for r in rows if r.day == today.isoformat()]),
                    week=_period([r for r in rows if r.day >= week_start]), month=m,
                    per_answer_inr=round(m.inr / m.requests, 2) if m.requests else 0.0, by_day=by_day, prices=PRICE)


def all_colleges() -> dict[str, Period]:
    """This month, per college (platform owner)."""
    month = _today()[:7]
    with SessionLocal() as db:
        rows = db.scalars(select(AssistantUsageRow)).all()
    out: dict[str, list] = {}
    for r in rows:
        if r.day[:7] == month:
            out.setdefault(r.org_id, []).append(r)
    return {org: _period(rs) for org, rs in out.items()}
