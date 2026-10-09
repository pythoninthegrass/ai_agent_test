Working rules for this repository.

1. One milestone per turn. Complete exactly the milestone you were asked for, commit it, then stop. Do not start the next milestone. After your final summary make no further tool calls.
2. Test first. Write the milestone's tests, run them, and confirm they fail for the expected reason before writing any implementation. Then implement and run the full suite until it is green. Write several focused tests per milestone covering edge cases and error paths, not a single smoke test.
3. Verify before claiming. Say a milestone is done only after the full test suite has just passed in this turn and `git status` shows nothing unexpected.
4. Commit hygiene. Before committing, run `git status`. Stage only the source and test files you changed: never `run.log`, `*.bak`, `__pycache__`, or other generated or log files. One commit per milestone with the requested message. Do not rewrite or reset history unless a commit is demonstrably wrong.
5. Keep the behavior of earlier milestones intact; run the whole suite every time.
6. If a command is rejected or fails twice the same way, change your approach instead of repeating it.
