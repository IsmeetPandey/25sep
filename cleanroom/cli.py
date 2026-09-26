from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import CleanRoomError, probe


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cleanroom",
        description="Detect hidden workspace files that influence a command.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-candidates", type=int, default=20)
    parser.add_argument("--include-ignored", action="store_true")
    parser.add_argument(
        "--observe",
        choices=("exit-code", "stdout-hash"),
        default="exit-code",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    try:
        report = probe(
            Path.cwd(),
            command,
            timeout=args.timeout,
            max_candidates=args.max_candidates,
            include_ignored=args.include_ignored,
            observe=args.observe,
        )
    except CleanRoomError as exc:
        print(f"cleanroom: {exc}", file=sys.stderr)
        return 2

    payload = {
        "command": list(report.command),
        "observe": report.observe,
        "worktree": report.worktree.__dict__,
        "cleanroom": report.cleanroom.__dict__,
        "candidates": [c.__dict__ for c in report.candidates],
        "different_from_cleanroom": report.worktree != report.cleanroom,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"worktree exit={report.worktree.exit_code}; "
            f"cleanroom exit={report.cleanroom.exit_code}"
        )
        if report.observe == "stdout-hash":
            print(
                f"worktree stdout_sha256={report.worktree.stdout_hash}; "
                f"cleanroom stdout_sha256={report.cleanroom.stdout_hash}"
            )
        hits = [c.path for c in report.candidates if c.matched]
        if hits:
            print("first-order candidate matches:")
            for path in hits:
                print(f"  {path}")
        elif report.worktree != report.cleanroom:
            print("behavior differs, but no single candidate reproduced it")
        else:
            print("no observed difference between worktree and clean-room")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
