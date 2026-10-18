#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Pass one .mailmd file to a batch launcher without expanding its filename."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


# -----------------------------------------------------------------------------
def launch(batch: Path, source: Path) -> int:
    """Run a batch launcher with exactly one selected .mailmd source path.

    Args:
        batch: Existing .bat file to execute.
        source: Existing .mailmd document passed to that launcher.

    Returns:
        The batch process exit code after it finishes, including any interactive
        retry.

    Raises:
        ValueError: The platform is not Windows or either path has an invalid
            extension or does not identify an existing file.
        OSError: The command processor cannot be started.

    Paths are passed through environment variables with delayed expansion
    disabled, so literal percent signs and exclamation marks are preserved. The
    launcher may save drafts or send messages according to the selected
    document's configuration.
    """
    if sys.platform != "win32":
        raise ValueError("Le lancement .bat nécessite Windows")
    batch, source = batch.resolve(), source.resolve()
    if batch.suffix.lower() != ".bat" or not batch.is_file():
        raise ValueError(f"Lanceur .bat introuvable : {batch}")
    if source.suffix.lower() != ".mailmd" or not source.is_file():
        raise ValueError(f"Fichier .mailmd introuvable : {source}")
    command_processor = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
    environment = {
        **os.environ,
        "PYOUTLOOKMAILING_BATCH": str(batch),
        "PYOUTLOOKMAILING_FILE": str(source),
        "PYOUTLOOKMAILING_PYTHON": sys.executable,
    }
    # cmd expands these variables once, leaving literal %NAME% and ! in
    # filenames
    # intact. No CALL (which would expand them twice) and no delayed expansion.
    command = (
        f'"{command_processor}" /d /v:off /s /c '
        '""%PYOUTLOOKMAILING_BATCH%" "%PYOUTLOOKMAILING_FILE%""'
    )
    return subprocess.run(
        command, executable=str(command_processor), env=environment, check=False
    ).returncode


# -----------------------------------------------------------------------------
def main(argv=None) -> int:
    """Parse the Explorer bridge arguments and return the batch exit status.

    argv is an argument list or None for sys.argv. Launch errors return 1 and
    show a Windows message box when available; argparse errors raise SystemExit.
    """
    parser = argparse.ArgumentParser(
        description="Process a .mailmd email through a batch launcher"
    )
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    try:
        return launch(args.batch, args.source)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0, str(exc), "pyoutlookmailing", 0x10
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
