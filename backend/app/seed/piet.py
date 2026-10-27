"""PIET (sample): the GNDEC sample data under another college's name, for showing how a new college is set up
from scratch (sign up, Setup, upload the department files, Generate). Student logins use ``@piet.test``, so the
college built from these files never shares accounts with the built-in demo colleges.

Run ``python -m app.seed.piet [folder]`` to write PIET_1_AS.xlsx ... PIET_5_CE.xlsx (default docs/demo-data/PIET).
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.seed.gndec import department_files

NAME = "Panipat Institute of Engineering and Technology"
DOMAIN = "piet.test"


def write_files(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    files = department_files(domain=DOMAIN, prefix="PIET", label="PIET (sample)",
                             note=("first year. Electives and pooled groups are added in Setup.",))
    written = []
    for name, content in files.items():
        (folder / name).write_bytes(content)
        written.append(folder / name)
    return written


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "docs" / "demo-data" / "PIET"
    for p in write_files(target):
        print(p)
