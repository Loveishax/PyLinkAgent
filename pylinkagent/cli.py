"""CLI entrypoints for PyLinkAgent."""

import os
import subprocess
import sys
from typing import Optional, Sequence


def _build_command(argv: Sequence[str]) -> list[str]:
    if not argv:
        raise SystemExit("usage: pylinkagent-run <command> [args...]")
    return list(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_command(sys.argv[1:] if argv is None else argv)
    env = os.environ.copy()
    env["PYLINKAGENT_ENABLED"] = "true"

    completed = subprocess.run(args, env=env, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
