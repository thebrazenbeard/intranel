# Intranel editor-startup regression — Engineer B safety repair

2026-11-18, source-only. The exact subject is Intranel main at ad9ee55dc5aba0882bdd93420d6e74b0e0c38f21.

## Verified cause

The October 31 documentation commit ad9ee55 reintroduced .vscode/tasks.json invoking a Node script in .vscode/ini on folderOpen, and task.allowAutomaticTasks in .vscode/settings.json. Prior security PR #14 had removed the mechanism in commit 0575f59; PR #16 added a CI guard. The source guard detects the current regression; no suspicious code was executed.

> A prior security merge, a clean README, or a CI trigger does not prove the current Git tree is safe. Host/editor and historical checkout states require separate investigation.

## Narrow repair and test

The proposed tree removes .vscode/ini and .vscode/tasks.json and restores settings.json to the exact clean Git blob 3861df39fdb913d4bac2616c0b2642b35dd3d462 from parent 498357b. A new test asserts the actual checkout remains startup-inert, alongside the existing mocked regression fixtures. It inspects historical Git blobs as data, without executing them.

On Lappy Windows with Python 3.12.10: source startup guard PASS; 167/167 Python unit tests PASS in normal and optimized mode; new direct-tree tests 3/3 PASS. Source-only, not hosted CI or deployed transport qualification.

Intranel protocol, private identities, authority, and A-owned mailbox remain untouched. Do not use public GitHub or public Bus as a confidential chat transport. A stored message is not proof of consumption by a separate ChatGPT recipient.