"""Request context: who is calling, and their membership in the college in the URL.

The org comes from the URL path, the user from the signed token, and the role from
the database membership: never from the request body (golden rule 5).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from fastapi import Depends, Header, HTTPException

from app.accounts import Member, get_user, membership
from app.core.security import decode_token
from app.db.models import UserRow
from app.store import OrgState, store


@dataclass
class Ctx:
    user: UserRow
    member: Member
    state: OrgState
    # False when this member sees the last published timetable while a newer draft waits: no edits then.
    live: bool = True


def current_user(authorization: str | None = Header(default=None)) -> UserRow:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please log in.")
    user_id = decode_token(authorization.split(" ", 1)[1])
    user = get_user(user_id) if user_id else None
    if user is None:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    return user


def org_ctx(org: str, user: UserRow = Depends(current_user)) -> Ctx:
    state = store.org(org)
    m = membership(user.id, org) if state else None
    if state is None or m is None:
        # Same answer whether the college doesn't exist or you're not in it: no tenant leaks.
        raise HTTPException(404, "College not found.")
    if m.role in ("teacher", "student"):
        # Teachers and students only ever see a published timetable.
        live = state.published is not None and state.published is state.timetable
        return Ctx(user=user, member=m, state=replace(state, timetable=state.published), live=live)
    return Ctx(user=user, member=m, state=state)


def allow(reason: str) -> None:
    """Raise 403 with the plain-language reason if a permission check failed."""
    if reason:
        raise HTTPException(403, reason)
