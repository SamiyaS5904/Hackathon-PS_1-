"""Reply language mirrors the user: English -> English, Roman Hinglish -> Roman Hinglish."""

import pytest

from app.language import detect, instruction

ENGLISH = [
    "When is my next DSA lab?",
    "Which rooms are free now in the main building?",
    "Move CSE-2B's Monday DBMS lecture to Friday morning",
    "Who is below 75% attendance in CSE-1A?",
    "Where is Dr. Kaur right now?",
    "Can I miss a class this week?",
    "Find a makeup time for my cancelled lecture",
    "Thanks!",
    "ok",
]
HINGLISH = [
    "kal mera pehla lecture kab hai",
    "aaj koi class cancel hui kya?",
    "Free rooms ke baare me batao",
    "CSE-2A ka DBMS lecture Friday ko shift karo",
    "meri attendance kitni hai",
    "Dr. Kaur abhi kahan hai?",
    "next week mujhe kab free time milega",
    "theek hai, apply kar do",
    "कल मेरा लेक्चर कब है",
]


@pytest.mark.parametrize("text", ENGLISH)
def test_english_stays_english(text):
    assert detect(text) == "english"


@pytest.mark.parametrize("text", HINGLISH)
def test_hinglish_is_mirrored(text):
    assert detect(text) == "hinglish"


def test_instruction_asks_for_roman_script():
    assert "no Devanagari" in instruction("hinglish")
    assert instruction("english") == "reply language: English"


def test_context_line_carries_the_reply_language_and_voice_hint():
    from app.main import ChatRequest, _context_line

    hi = _context_line(ChatRequest(org="demo", message="kal mera lecture kab hai", voice=True, lang="auto"), "2026-10-26", "09:00")
    assert "reply language: Hinglish" in hi and "Spoken message" in hi
    en = _context_line(ChatRequest(org="demo", message="When is my next lecture?"), "2026-10-26", "09:00")
    assert en.endswith("reply language: English.") and "Spoken" not in en



def test_english_is_the_default_reply_language():
    from app.main import ChatRequest, _context_line

    line = _context_line(ChatRequest(org="demo", message="kal mera lecture kab hai"), "2026-10-26", "09:00")
    assert line.endswith("reply language: English.")
    hi = _context_line(ChatRequest(org="demo", message="when is my lecture", lang="hinglish"), "2026-10-26", "09:00")
    assert "reply language: Hinglish" in hi
