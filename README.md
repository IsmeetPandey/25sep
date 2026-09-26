# CleanRoom

CleanRoom checks whether a command's behavior depends on files that are not part of the tracked Git tree.

It creates an isolated snapshot containing the repository's current tracked state, deliberately leaves out untracked and ignored files, runs the command there, and compares the result with the real working tree. When the results differ, it can test individual candidate files without touching the user's working tree.

This targets a common debugging gap: Git can make a pristine tree for testing, but doing that destructively can erase the evidence you needed. CleanRoom turns the question into a non-destructive diagnostic.

## What it proves

CleanRoom is a differential diagnostic, not a formal causal proof.

- exit-code observes whether the command exits differently.
- stdout-hash compares a SHA-256 digest of stdout without storing the output.
- First-order attribution tests candidate files one at a time. Multiple files can interact, so a missing single-file hit does not prove that no hidden state matters.

## Install

Requires Python 3.10+ and Git.

~~~bash
python -m pip install -e .
~~~

## Use

From a Git worktree:

~~~bash
cleanroom -- python -m pytest -q
cleanroom --observe stdout-hash -- python -m build
~~~

Useful options:

~~~text
--timeout SECONDS
--max-candidates N
--include-ignored
--observe exit-code|stdout-hash
~~~

CleanRoom never calls a shell. The command is executed with an argument vector exactly as supplied after the separator.

## Safety model

CleanRoom never deletes, cleans, resets, checks out, or writes to the user's worktree. Trials happen in temporary directories.

Candidate symlinks are skipped. Individual candidate files larger than 4 MiB are skipped. Every trial has a timeout.

The clean snapshot contains current tracked content, including staged and unstaged tracked changes, but excludes untracked and ignored files. Runtime state outside the workspace is not isolated.

## Development

~~~bash
python -m unittest discover -s tests -v
PYTHONPATH=. python -m cleanroom.cli --help
~~~

## Why not git clean?

Git clean is useful for producing a pristine working directory, including optionally removing ignored files, but it is destructive. CleanRoom performs the comparison in isolated temporary directories instead.

## License

MIT
