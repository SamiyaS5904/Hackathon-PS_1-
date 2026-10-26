"""Plain college language: no solver or software jargon in anything a college user reads.

Scans the web app's rendered text (JSX text and sentence-like strings) and the backend's user-facing messages
(errors, problems, notifications) for words a College Admin shouldn't have to know."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANNED = re.compile(r"\b(tenant|solver|cp-sat|constraint|allotment|override|session)s?\b", re.IGNORECASE)
JSX_TEXT = re.compile(r">([^<>{}]*[A-Za-z][^<>{}]*)<")
STRING = re.compile(r"""(["'`])((?:(?!\1).)*\s(?:(?!\1).)*)\1""")
USER_FACING_PY = re.compile(r"(HTTPException\(|\.append\(|send\(|message=|summary=|missing=)")


def _sentences(line: str) -> list[str]:
    out = [m.group(1) for m in JSX_TEXT.finditer(line)]
    for m in STRING.finditer(line):
        text = m.group(2)
        # Sentences only: skip class lists, paths, ids and code.
        if re.search(r"\b(px|py|text|bg|rounded|flex|grid|border)-", text) or "/" in text and " " not in text.strip():
            continue
        if re.search(r"[a-z]\s+[a-z]", text, re.IGNORECASE):
            out.append(text)
    return out


def test_web_app_text_has_no_jargon():
    hits = []
    for path in (ROOT / "frontend").glob("**/*.ts*"):
        if "node_modules" in path.parts or ".next" in path.parts or path.suffix not in (".ts", ".tsx"):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = re.sub(r"\s//\s.*$", "", line)  # a trailing code comment isn't shown to anyone
            s = line.strip()
            if s.startswith(("import ", "//", "*", "/*")) or "className=" in s and not JSX_TEXT.search(s):
                continue
            for text in _sentences(line):
                if BANNED.search(text):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {text.strip()[:80]}")
    assert not hits, "Jargon in the web app:\n" + "\n".join(hits)


def test_backend_messages_have_no_jargon():
    hits = []
    for path in (ROOT / "backend" / "app").glob("**/*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not USER_FACING_PY.search(line) or line.strip().startswith("#"):
                continue
            for m in STRING.finditer(line):
                if re.search(r"[a-z]\s+[a-z]", m.group(2), re.IGNORECASE) and BANNED.search(m.group(2)):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {m.group(2).strip()[:80]}")
    assert not hits, "Jargon in user-facing backend messages:\n" + "\n".join(hits)
