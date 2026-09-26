from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cleanroom.core import candidate_paths, probe


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    (path / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)


class CleanRoomTests(unittest.TestCase):
    def test_candidate_paths_omits_ignored_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            init_repo(root)
            (root / "visible.txt").write_text("v", encoding="utf-8")
            (root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "ignore"], cwd=root, check=True)
            (root / "ignored.txt").write_text("i", encoding="utf-8")
            self.assertEqual(candidate_paths(root, False), ["visible.txt"])

    def test_exit_code_detects_hidden_file_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            init_repo(root)
            (root / "secret.txt").write_text("ready\n", encoding="utf-8")
            result = probe(
                root,
                [sys.executable, "-c", "import pathlib; raise SystemExit(0 if pathlib.Path('secret.txt').exists() else 1)"],
                max_candidates=10,
            )
            self.assertEqual(result.worktree.exit_code, 0)
            self.assertEqual(result.cleanroom.exit_code, 1)
            self.assertTrue(result.candidates[0].matched)

    def test_unmodified_repo_has_same_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            init_repo(root)
            result = probe(root, [sys.executable, "-c", "raise SystemExit(0)"])
            self.assertEqual(result.worktree.exit_code, result.cleanroom.exit_code)

    def test_stdout_hash_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            init_repo(root)
            result = probe(root, [sys.executable, "-c", "print('hello')"], observe="stdout-hash")
            self.assertEqual(result.worktree.stdout_hash, result.cleanroom.stdout_hash)
            self.assertTrue(result.worktree.stdout_hash)

    def test_max_candidates_limits_trials(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            init_repo(root)
            for i in range(5):
                (root / f"candidate{i}.txt").write_text(str(i), encoding="utf-8")
            result = probe(root, [sys.executable, "-c", "raise SystemExit(0)"], max_candidates=2)
            self.assertEqual(len(result.candidates), 2)


if __name__ == "__main__":
    unittest.main()
