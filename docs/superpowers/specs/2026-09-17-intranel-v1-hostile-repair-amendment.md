# Intranel V1 Independent Hostile-Review Amendment

Date: 2026-09-17
Status: `REPAIR_SOURCE_CANDIDATE / NOT_INDEPENDENTLY_REQUALIFIED / DRAFT_PR`

Current repaired executable source subject: `9cd1ba4d4da67c42bc9a186818c9229213b6c762`.

This amendment supersedes the affected semantics in `2026-09-17-intranel-v1-design.md` without rewriting that earlier design's historical provenance. The normative protocol remains `spec/INTRANEL_1.md`.

## Why the amendment exists

The first independent hostile review found that the initial V1 implementation could look fail-closed while still relying on sender-controlled or insufficiently bound receiver state. In particular, effect classification, receiver checks, nested semantic mutability, constraints/prohibitions, cancellation, security-profile attestation, receipt semantics, schema parity, canonical numeric behavior, and resource limits needed stronger boundaries.

A subsequent BT2 hostile pass found one additional idempotency edge case: an identical retry of a verified-complete cancellation could be forced through current target-cancellability evaluation before its completed prior operation was recognized. That ordering contradicted the general completed-operation `DUPLICATE` rule.

## Amended trust model

1. `effect_class` is sender-declared protocol data. A receiver-owned action/handler classifier establishes `ReceiverEvidence.effective_effect_class`; `EXECUTE`/`CANCEL` cannot proceed when that classification is unknown or disagrees with the wire claim.
2. Receiver admission evidence is bound to the exact content digest, operation digest when present, origin, actor, target, exact subject, and authority reference. It is not reusable across nearby packets.
3. Payload and receipt JSON are recursively copied/frozen at construction. Later caller mutation cannot alter an admitted message or digest.
4. Non-empty constraints/prohibited effects require explicit bound receiver evaluation; unknown state quarantines and known violation rejects.
5. `security_profile` never self-attests transport protection. Admission requires receiver evidence that the requested profile was actually satisfied.
6. `CANCEL` separates the cancellation request operation from `target_operation_id` and requires exact target-state cancellability evidence for a cancellation that has not already completed.
7. Once exact-message trust/effect/authority checks pass, an identical verified-complete prior operation returns `DUPLICATE` before any attempt to re-evaluate the old cancellation target. The target is not re-cancelled.
8. `RECEIPT` is a bound receipt claim, not an oracle of effect truth; independent readback/verification remains necessary.
9. Parser/schema semantic rules are exercised by one shared valid/invalid corpus using a real Draft 2020-12 validator.
10. Canonical JSON uses a narrow cross-runtime subset: printable-ASCII keys, UTF-8 values, safe integral numeric values, integral floats normalized to integers, and non-integral floats forbidden.
11. Explicit depth/node/collection/string/token/message limits are enforced before semantic state is treated as admissible.

## Current verification boundary

A reconstructed workspace from the current repaired branch content passed 83 unit/hostile/schema/vector tests plus compile verification under CPython 3.13.5. Private-repository GitHub-hosted Actions remain unavailable as qualification evidence because jobs fail before runner assignment. Native CPython 3.12 qualification therefore remains unresolved.

Passing this local regression suite is not independent hostile requalification. The repaired exact source subject must be rereviewed. No merge, deployment, installation, key operation, provider change, or Bus topology mutation is implied or authorized by this amendment.
