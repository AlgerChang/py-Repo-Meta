from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)

    pyinstaller_run(
        [
            "--clean",
            "-F",
            "-n",
            "py-repo-meta",
            "--paths",
            "src",
            "--distpath",
            "dist",
            "--workpath",
            "build",
            "--specpath",
            ".",
            "src/repometa/cli.py",
            "--optimize",
            "2",
        ]
    )


if __name__ == "__main__":
    main()
