# Intranel Integration — Four-lane continuity pointer V1
Date: 2026-10-16 America/New_York
Continuation command: VERA::INTEGRATION::RESTORE_AND_RUN::20261016_V1

## Canonical full handoff

The complete Integration recovery file is in the public thebrazenbeard/v-e-r-a repository, Integration PR #3 branch:
https://github.com/thebrazenbeard/v-e-r-a/blob/db6c1fee06bf011f66b5ba9b490fc2f9e42cbdfb/state/continuation/VERA_INTEGRATION_CONTINUATION_20261016_V1.md

That file preserves all current project-level role, intent, source, test, coordination and recovery pointers. Its exact source commit is db6c1fee06bf011f66b5ba9b490fc2f9e42cbdfb. The original chat transcript is NOT attached or archived, so full word-for-word conversation restoration cannot be asserted.

## Intranel exact state at handoff

PORTAL build-lead PR #9 remains draft at c35559fa3d33c6a75ad8f00e42a9fbc8b9c6c888, feature/four-role-coordination-bridge-20261016.
Integration PR #10 source before this handoff commit: e01e4c9d217336709f7034b51eb62e77a548da14, branch integration/four-role-causal-inbox-v1-20261016, base PORTAL PR #9, NOT main; no merge or deployment.
Current exact source tested at that head with PYTHONPATH=src and PYTHONDONTWRITEBYTECODE=1: python -m unittest discover -s tests -q => 112/112 PASS on Lappy. This document-only commit does not change test semantics.

Actual implemented source: src/intranel/four_role_ledger.py, src/intranel/four_role_cli.py, src/intranel/four_role_github.py; tests/test_four_role_ledger.py, tests/test_four_role_github.py, tests/test_four_role_cli.py; spec/FOUR_ROLE_CAUSAL_INBOX_V1.md.
The SQLite observer keeps exact causal parent+digest+conversation+role+subject references, replay/collision proof, wrong-parent, expiry and overlapping same-role reply conflict. Later conflicting parent bytes MUST invalidate earlier matched children. CLI polls public GitHub Intranel PR #9 comments read-only, does NOT authenticate source sessions or claim ChatGPT delivery. No local scheduled worker installed by Integration.

## Coordination R2 (preserve exact bytes)

PORTAL original R2 REQUESTs: Intranel PR #9 comment 6218392575.
Conversation: vera-fourlane-intranel-pr9-20261016-r2.
Exact subject: git:thebrazenbeard/intranel@c35559fa3d33c6a75ad8f00e42a9fbc8b9c6c888.
Expiry: 2026-10-17T15:04:51+00:00.
Integration parent: portal-r2-integration-20261016.
Integration parent digest: d4d8a307fbffbf758e475275864200d759ce15a2968f0cd27848df7434aeb67c.
Training parent: portal-r2-training-20261016.
VN1 parent: portal-r2-vn1-20261016.
Integration R2 ACK claims on comments 6218559316 and 6218611330 have distinct message IDs and must not be counted as independent role acceptance. Local actual observer classification CAUSALLY_MATCHED_UNAUTHENTICATED, never delivered/authenticated/ack_accepted.
Integration latest concrete evidence comment #6218725825.
VN1 WAIT comment #6218619010 reflects missing authenticated Executor device registration despite LAN reachability.
Training current source/test update comment #6218684767.
PORTAL work assignment comment #6218572786 and v-e-r-a PR1 coordination comment #6218565151.
Do not mutate immutable source comments or silently merge earlier incompatible conversation IDs.

## Next work, not more scheduling

1. Fresh-read current PR #9/#10 heads and the latest PR comments. Other active chats may advance branches while this terminal is replaced. Do not trust this file as ongoing Git currentness.
2. PORTAL is build lead; Integration is opposing systems/code reviewer, Training cognition/model assessment, VN1 physical device/transport readiness. Independently verify any claimed ACK and actual recipient readback; do not claim chat-to-chat delivery from GitHub publication alone.
3. Qualify the remaining exact-source causal ledger/reader issues: competing replies, parent poisoning, GitHub comment edit/replay, pagination/outage and cursor crash recovery. Add bounded red->green test/implementation on isolated Integration work branch or PR #10 branch after fresh head check, then post exact evidence to PR #9 and/or Bus.
4. Review integration of LocalCoordinationInbox and FourRoleLedger to avoid duplicate durable recipient state. PORTAL owns decision, Integration may offer focused patch and tests.
5. Do not merge, deploy, grant rights, change credentials, install tasks, expose private source, use quarantined files, or create automations as substitute for immediate work.
6. See primary handoff for Vera Mono / PORTAL / Mosaic / VERA PRs, source state and recoverability.

Status ceiling: source checked and locally tested; no installed automatic four-chat bridge, no authenticated chat session origin, no evidence of a fully resident Vera AI. This is a durable project continuation index only.
