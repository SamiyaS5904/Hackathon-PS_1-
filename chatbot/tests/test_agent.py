"""Agent loop with a fake Claude client: tool round-trip, events, request settings, append-only history."""

import asyncio
from types import SimpleNamespace

import pytest

from app.agent import Conversation, run_turn
from app.tools import ToolContext, ToolError, run_tool
from tests.conftest import ADMIN, STUDENT


class FakeStream:
    def __init__(self, message, texts):
        self.message, self.texts = message, texts

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        async def gen():
            for t in self.texts:
                yield SimpleNamespace(type="text", text=t)
        return gen()

    async def get_final_message(self):
        return self.message


class FakeClient:
    """Plays back scripted turns and records each request's keyword arguments."""

    def __init__(self, turns):
        self.turns, self.requests = list(turns), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        message, texts = self.turns.pop(0)
        return FakeStream(message, texts)


def tool_use(name, inp, bid="tu1"):
    return SimpleNamespace(type="tool_use", id=bid, name=name, input=inp)


def text(t):
    return SimpleNamespace(type="text", text=t)


async def collect(gen):
    return [ev async for ev in gen]


def test_tool_round_trip_and_answer(backend):
    client = FakeClient([
        (SimpleNamespace(stop_reason="tool_use", content=[tool_use("my_schedule", {"from_date": "2026-10-19"})]), []),
        (SimpleNamespace(stop_reason="end_turn", content=[text("You have Maths at 09:00.")]),
         ["You have ", "Maths at 09:00."]),
    ])
    conv = Conversation(owner="u", org="c")
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="08:00")
    events = asyncio.run(collect(run_turn(client, conv, ctx, "Sunrise College", "What do I have today?",
                                          "Context: today is Mon 2026-10-19")))
    kinds = [e["type"] for e in events]
    assert kinds == ["tool", "tool", "token", "token", "done"]
    assert events[0]["status"] == "start" and events[1]["status"] == "done"
    # History is append-only: user, assistant(tool_use), user(tool_result), assistant(answer).
    assert [m["role"] for m in conv.messages] == ["user", "assistant", "user", "assistant"]
    assert conv.messages[2]["content"][0]["type"] == "tool_result"
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5" and req["fallbacks"] == "default"
    assert req["output_config"]["effort"] == "medium" and req["thinking"] == {"type": "adaptive"}
    assert "tool_choice" not in req  # forced tool use isn't supported on this model
    assert "propose_move" not in {t["name"] for t in req["tools"]}  # students never see edit tools
    assert "Aarav" in req["system"][0]["text"] and "2026-10-19" not in req["system"][0]["text"]  # stable prompt


def test_proposal_card_is_emitted_and_tool_errors_flow_back(backend):
    client = FakeClient([
        (SimpleNamespace(stop_reason="tool_use", content=[
            tool_use("propose_move", {"session_id": "m1", "day": "Wed", "start_time": "09:00"}, "a"),
            tool_use("propose_move", {"session_id": "m1", "day": "Mon", "start_time": "12:00"}, "b")]), []),
        (SimpleNamespace(stop_reason="end_turn", content=[text("Prepared.")]), ["Prepared."]),
    ])
    conv = Conversation(owner="u", org="c")
    ctx = ToolContext(backend=backend, member=ADMIN, today="2026-10-19", now="08:00")
    events = asyncio.run(collect(run_turn(client, conv, ctx, "Sunrise College", "Move maths to Wednesday 9",
                                          "Context")))
    cards = [e for e in events if e["type"] == "card"]
    assert len(cards) == 1 and cards[0]["card"]["proposal"]["id"] == "p-1"
    results = conv.messages[2]["content"]
    assert len(results) == 2  # all tool results in one message
    assert results[1]["is_error"] and "lunch" in results[1]["content"]


def test_refusal_and_step_limit(backend):
    refusal = FakeClient([(SimpleNamespace(stop_reason="refusal", content=[]), [])])
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="08:00")
    events = asyncio.run(collect(run_turn(refusal, Conversation("u", "c"), ctx, "S", "hi", "Context")))
    assert any("can't help" in e.get("text", "") for e in events) and events[-1]["type"] == "done"

    loop = FakeClient([(SimpleNamespace(stop_reason="tool_use",
                                        content=[tool_use("free_rooms", {}, f"x{i}")]), []) for i in range(10)])
    events = asyncio.run(collect(run_turn(loop, Conversation("u", "c"), ctx, "S", "rooms?", "Context")))
    assert any(e["type"] == "error" and "too many steps" in e["message"] for e in events)


def test_student_cannot_ask_for_others_free_time(backend):
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="08:00")
    with pytest.raises(ToolError, match="own free time"):
        asyncio.run(run_tool(ctx, "free_time", {"from_date": "2026-10-19", "who": "Prof. Ravi Kumar"}))


def test_text_from_separate_steps_gets_a_paragraph_break(backend):
    client = FakeClient([
        (SimpleNamespace(stop_reason="tool_use", content=[text("Let me look."), tool_use("free_rooms", {})]),
         ["Let me look."]),
        (SimpleNamespace(stop_reason="end_turn", content=[text("LH-101 is free.")]), ["LH-101 ", "is free."]),
    ])
    ctx = ToolContext(backend=backend, member=STUDENT, today="2026-10-19", now="08:00")
    events = asyncio.run(collect(run_turn(client, Conversation("u", "c"), ctx, "S", "free rooms?", "Context")))
    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert tokens == ["Let me look.", "\n\nLH-101 ", "is free."]
