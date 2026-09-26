from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Sequence

MAX_CANDIDATE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class Observation:
    kind: str
    exit_code: int
    stdout_hash: str | None = None


@dataclass(frozen=True)
class CandidateResult:
    path: str
    matched: bool
    reason: str


@dataclass(frozen=True)
class ProbeReport:
    command: tuple[str, ...]
    observe: str
    worktree: Observation
    cleanroom: Observation
    candidates: tuple[CandidateResult, ...]


class CleanRoomError(RuntimeError):
    pass


def _git(args: Sequence[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=cwd, check=True,
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    return completed.stdout


def repo_root(cwd: Path) -> Path:
    try:
        return Path(_git(["rev-parse", "--show-toplevel"], cwd).strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise CleanRoomError("not inside a Git worktree") from exc


def candidate_paths(root: Path, include_ignored: bool) -> list[str]:
    paths = {
        p.strip()
        for p in _git(["ls-files", "--others", "--exclude-standard"], root).splitlines()
        if p.strip()
    }
    if include_ignored:
        status = _git(
            ["status", "--porcelain=v1", "--ignored=matching", "--untracked-files=all"],
            root,
        )
        paths.update(
            line[3:].strip() for line in status.splitlines() if line.startswith("!! ")
        )
    return sorted(paths)


def _copy_candidate(root: Path, destination: Path, rel: str) -> str:
    src = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        src.relative_to(root_resolved)
    except ValueError as exc:
        raise CleanRoomError(f"candidate escapes repository: {rel}") from exc
    if src.is_symlink():
        return "skipped: symlink"
    if not src.is_file():
        return "skipped: not a regular file"
    if src.stat().st_size > MAX_CANDIDATE_BYTES:
        return "skipped: file exceeds 4 MiB limit"
    target = destination / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return "copied"


def _make_clean_snapshot(root: Path, destination: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"],
        cwd=root, check=True, capture_output=True,
    )
    subprocess.run(
        ["tar", "-xf", "-", "-C", str(destination)],
        input=archive.stdout, check=True, capture_output=True,
    )
    tracked_patch = _git(["diff", "--binary", "HEAD"], root)
    if tracked_patch:
        patch = destination / ".cleanroom-tracked.patch"
        patch.write_text(tracked_patch, encoding="utf-8")
        try:
            subprocess.run(
                ["git", "apply", "--binary", patch.name],
                cwd=destination, check=True, capture_output=True, text=True,
            )
        finally:
            patch.unlink(missing_ok=True)


def _run(command: Sequence[str], cwd: Path, timeout: float, observe: str) -> Observation:
    try:
        completed = subprocess.run(
            list(command), cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if observe == "stdout-hash" else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, text=False, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return Observation(observe, 124, None)
    digest = (
        hashlib.sha256(completed.stdout or b"").hexdigest()
        if observe == "stdout-hash" else None
    )
    return Observation(observe, completed.returncode, digest)


def probe(cwd: Path, command: Sequence[str], *, timeout: float = 30.0,
          max_candidates: int = 20, include_ignored: bool = False,
          observe: str = "exit-code") -> ProbeReport:
    if not command:
        raise CleanRoomError("a command is required after the separator")
    if observe not in {"exit-code", "stdout-hash"}:
        raise CleanRoomError("observe must be exit-code or stdout-hash")
    if timeout <= 0:
        raise CleanRoomError("timeout must be positive")
    if max_candidates < 0:
        raise CleanRoomError("max-candidates cannot be negative")

    root = repo_root(cwd)
    worktree_obs = _run(command, root, timeout, observe)

    with tempfile.TemporaryDirectory(prefix="cleanroom-") as raw:
        clean = Path(raw) / "clean"
        clean.mkdir()
        _make_clean_snapshot(root, clean)
        clean_obs = _run(command, clean, timeout, observe)

        results: list[CandidateResult] = []
        for rel in candidate_paths(root, include_ignored)[:max_candidates]:
            trial = Path(raw) / f"candidate-{len(results)}"
            shutil.copytree(clean, trial, symlinks=True)
            state = _copy_candidate(root, trial, rel)
            if state != "copied":
                results.append(CandidateResult(rel, False, state))
                shutil.rmtree(trial, ignore_errors=True)
                continue
            observed = _run(command, trial, timeout, observe)
            matched = observed == worktree_obs and observed != clean_obs
            results.append(
                CandidateResult(
                    rel,
                    matched,
                    "candidate reproduces worktree observation"
                    if matched else "no first-order match",
                )
            )
            shutil.rmtree(trial, ignore_errors=True)

    return ProbeReport(
        tuple(command), observe, worktree_obs, clean_obs, tuple(results)
    )
