# Intranel V1 Independent Hostile-Review Amendment

Date: 2026-09-17
Status: `REPAIR_SOURCE_CANDIDATE / NOT_INDEPENDENTLY_REQUALIFIED / DRAFT_PR`

Independent hostile-review subject: `b7a8c08483a6f7cdce9323b39a83ef86e96e748f`.

This amendment supersedes the affected semantics in `2026-09-17-intranel-v1-design.md` without rewriting that earlier design's historical provenance. The normative protocol remains `spec/INTRANEL_1.md`.

## Why the amendment exists

The first independent hostile review found that the initial V1 implementation could look fail-closed while still relying on sender-controlled or insufficiently bound receiver state. In particular, effect classification, receiver checks, nested semantic mutability, constraints/prohibitions, cancellation, security-profile attestation, receipt semantics, schema parity, canonical numeric behavior, and resource limits needed stronger boundaries.

## Amended trust model

1. `effect_class` is sender-declared protocol data. A receiver-owned action/handler classifier establishes `ReceiverEvidence.effective_effect_class`; `EXECUTE`/`CANCEL` cannot proceed when that classification is unknown or disagrees with the wire claim.
2. Receiver admission evidence is bound to the exact content digest, operation digest when present, origin, actor, target, exact subject, and authority reference. It is not reusable across nearby packets.
3. Payload and receipt JSON are recursively copied/frozen at construction. Later caller mutation cannot alter an admitted message or digest.
4. Non-empty constraints/prohibited effects require explicit bound receiver evaluation; unknown state quarantines and known violation rejects.
5. `security_profile` never self-attests transport protection. Admission requires receiver evidence that the requested profile was actually satisfied.
6. `CANCEL` separates the cancellation request operation from `target_operation_id` and requires exact target-state cancellability evidence.
7. `RECEIPT` is a bound receipt claim, not an oracle of effect truth; independent readback/verification remains necessary.
8. Parser/schema semantic rules are exercised by one shared valid/invalid corpus using a real Draft 2020-12 validator.
9. Canonical JSON uses a narrow cross-runtime subset: printable-ASCII keys, UTF-8 values, safe integral numeric values, integral floats normalized to integers, and non-integral floats forbidden.
10. Explicit depth/node/collection/string/token/message limits are enforced before semantic state is treated as admissible.

## Qualification boundary

Passing local regression tests or a self-review of these repairs is not independent hostile requalification. The repaired exact head must be rereviewed. No merge, deployment, installation, key operation, provider change, or Bus topology mutation is implied or authorized by this amendment.
