"""Assemble the Hugging Face Space folder: backend + assistant code, Dockerfile, start script, Space README.

    python deploy/make_hf_space.py

Writes deploy/_hf_space/ (git-ignored), leaving out secrets (.env), virtual environments, caches, local databases
and tests. Then push that folder to your Space (steps in docs/DEPLOY.md).
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deploy" / "_hf_space"
SKIP = shutil.ignore_patterns(".env", ".env.*", ".venv", "__pycache__", "*.pyc", ".pytest_cache", "*.db", "*.db-*",
                              "tests", ".ruff_cache")


def main() -> None:
    keep_git = (OUT / ".git").exists()  # re-running keeps the Space's git history
    if OUT.exists():
        for item in OUT.iterdir():
            if item.name == ".git":
                continue
            shutil.rmtree(item) if item.is_dir() else item.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("backend", "chatbot"):
        shutil.copytree(ROOT / name, OUT / name, ignore=SKIP)
    space = ROOT / "deploy" / "hf-space"
    shutil.copy(space / "Dockerfile", OUT / "Dockerfile")
    shutil.copy(space / "README.md", OUT / "README.md")
    # Linux needs LF line endings in the start script, whatever this checkout uses.
    (OUT / "start.sh").write_bytes((space / "start.sh").read_bytes().replace(b"\r\n", b"\n"))
    for leaked in OUT.rglob(".env"):
        raise SystemExit(f"Refusing: a secret file would be published: {leaked}")
    print(f"Space folder ready: {OUT}" + (" (git history kept)" if keep_git else ""))


if __name__ == "__main__":
    main()
