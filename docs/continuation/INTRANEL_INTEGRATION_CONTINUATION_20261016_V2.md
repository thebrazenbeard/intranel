# Intranel Integration — continuation V2 companion pointer

**New-chat restore token:** VERA::INTEGRATION::RESTORE_AND_RUN::20261016_V2

**Checked cut:** 2026-10-16 approximately 15:48 UTC. This is a companion index to the complete source-bound Integration V2 handoff in the public V-E-R-A repository:

**Primary currentness/operational record:** https://github.com/thebrazenbeard/v-e-r-a/blob/ee50943f7aa20c45071f57f3d8e5ff5e9c6f39cd/state/continuation/VERA_INTEGRATION_CONTINUATION_20261016_V2.md

**Historical full context (do not treat stale heads as current):** https://github.com/thebrazenbeard/v-e-r-a/blob/db6c1fee06bf011f66b5ba9b490fc2f9e42cbdfb/state/continuation/VERA_INTEGRATION_CONTINUATION_20261016_V1.md

**Intranel V1 checkpoint retained:** [INTRANEL_INTEGRATION_CONTINUATION_20261016_V1.md](./INTRANEL_INTEGRATION_CONTINUATION_20261016_V1.md). Preserve V1's earlier 112-test exact subject, but do not apply that qualification to subsequent code without testing.

## Exact current Integration source at handoff

- PORTAL build-lead [Intranel Draft PR #9](https://github.com/thebrazenbeard/intranel/pull/9): head `c35559fa3d33c6a75ad8f00e42a9fbc8b9c6c888`, open/unmerged as read at 15:48 UTC.
- Integration [Intranel Draft PR #10](https://github.com/thebrazenbeard/intranel/pull/10): source `38d7a4f0902e55c63c914c9236b761e7eae6eaef`, stacked on PORTAL's PR #9 branch (NOT main), open/unmerged at the checkpoint.
- Integration exact-source Lappy regression just repeated at that head: `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -q` => **123 / 123 PASS**, zero failures, actual local test run. This handoff adds only documentation and does not requalify installed services.
- Other lane's current code may advance this PR head concurrently. Always read the current exact head, staging status and PR discussion again in the new chat.

## Actual code and disposition

`src/intranel/four_role_ledger.py`: durable SQLite observations and causal REQUEST/ACK/WAIT/CONFLICT relations. Same-ID different canonical bytes -> immutable collision evidence; parent REQUEST collision poisons even a formerly matched child; competing same-role replies to one parent cannot be counted as independent votes. Both results remain untrusted declarative messages.

`src/intranel/four_role_github.py` and `four_role_cli.py`: actual bounded **read-only public PR #9 comment polling** with GitHub provider source locator, ingestion/replay/digest/shape controls. It does **not** authenticate a chat, deliver to ChatGPT, grant effect authority or install an active listener.

`src/intranel/four_role_reconcile.py`: newer read-only diagnostics between PORTAL's `LocalCoordinationInbox` and Integration's `FourRoleLedger`. Detects split writes, missing/mismatched/poisoned observations and inconsistent receiver bindings. Returns HOLD on conflict; positive `SNAPSHOT_AGREEMENT_UNATTESTED` is **not atomic**, especially under concurrent writers. PORTAL owns deciding one authoritative inbox or safe reconciliation strategy. The separate durable stores are **not installed as one production runtime**.

## PORTAL R2 immutable coordination

See canonical coordinator [PR9 comment #6218392575](https://github.com/thebrazenbeard/intranel/pull/9#issuecomment-6218392575).

- Round: `vera-fourlane-intranel-pr9-20261016-r2`.
- Exact subject: `git:thebrazenbeard/intranel@c35559fa3d33c6a75ad8f00e42a9fbc8b9c6c888`.
- Integration parent `portal-r2-integration-20261016`; digest `d4d8a307fbffbf758e475275864200d759ce15a2968f0cd27848df7434aeb67c`.
- Two independently staged **claims** of Integration ACK to that one parent: comments [#6218559316](https://github.com/thebrazenbeard/intranel/pull/9#issuecomment-6218559316) and [#6218611330](https://github.com/thebrazenbeard/intranel/pull/9#issuecomment-6218611330). They are competing same-role claims to be reconciled, **not two votes** or confirmation that PORTAL received the messages.
- Training also has competing R2 message claims, preserved unchanged. VN1 initially reported WAIT for missing Executor registration, then later reported generation-6 recovery plus a benign direct VN1 host command (comment #6219097469): separate time-bounded states, no reboot/failover guarantee.
- PORTAL's four fronts now proceed in **parallel**, per [V-E-R-A PR #1 comment #6218853006](https://github.com/thebrazenbeard/v-e-r-a/pull/1#issuecomment-6218853006), not a new series of scheduled ChatGPT tasks.
- No live automatic four-chat delivery, independently authenticated identity, recipient-owned acceptance, or protected execution was qualified by Integration.

## Resume work immediately, not by automation

1. Read the **full V-E-R-A V2 and V1 files**, then read this V2 and Intranel V1. Fresh-read PR #9/#10 exact heads, latest comments and PORTAL's current collision/ownership register.
2. Re-run current exact-head Intranel tests before edits. Work in an isolated branch/worktree; never overwrite concurrent Integration commits, force-push or touch PORTAL PR #9's source branch.
3. Highest-value executable defect: prove what happens when one inbox commits a packet but the other database/cursor crashes, and propose the smallest **single authoritative receiver-owned** storage/commit/replay fix. The read-only reconciler is diagnostic, not completed integration. Also test GitHub comment edits and pagination if source evidence supports.
4. Cross-review Vera Mono task-currentness and PORTAL's execution boundary. Keep no-effect advisory results separate from actual effect grants. Preserve individuality, dissent and separate local cognitive states.
5. Report actual test/source/readback to PORTAL and Communication Bus with exact head; never manufacture ACK, completion or installed transport.

**Safety:** user forbade delaying work by making recurring tasks; do not schedule. No merge/deploy, credentials, permissions, privacy violation, quarantined file publication, or destructive cleanup. Original repo authoritative; this source checkpoint is not a Lantern admission. WoWSQL `bt2-479e4ad9` was **not** consulted; no current Lantern cut claim.

**Evidence ceiling:** This text preserves current engineering context and pointers, not a literal exported transcript, hidden chain of thought, or continuous AI identity. New live Git/host evidence outranks it.
