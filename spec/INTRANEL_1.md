# INTRANEL/1

`INTRANEL/1` is the first semantic protocol for communication inside the Vera intranel network. The protocol is designed for machine coordination among Vera chats/lanes and other explicitly addressed infrastructure without relying on natural-language implication for governance-significant meaning.

## Core rule

A syntactically valid Intranel message is data, not permission. **Transport does not grant authority.** Authentication, confidentiality, routing, possession of a protocol implementation, or receipt over a trusted transport does not by itself authorize the requested effect.

Receivers independently validate identity, authority, exact subject, freshness/replay, capabilities, constraints, and effect class before acting.

## Identity and routing

Each message separates:

- `origin`: semantic author;
- `actor`: current transmitter or relay;
- `target`: processing/acting recipient;
- `reply_to`: response route.

A relay may change `actor`. It must not silently change `origin`. Neither direction implies authority transfer.

Addresses use `<namespace>:<node>`, for example `vera:primary`, `vera:lane/bv`, `radar:reviewer`, and `bus:vera-v2`.

## Correlation identity

- `message_id`: one packet instance;
- `operation_id`: one logical operation across retry/relay;
- `parent_message_id`: immediate causal parent when present;
- `conversation_id`: workflow/thread correlation.

A new `message_id` with the same verified `operation_id` is not permission to repeat a mutation. Idempotency is operation-bound.

## Performatives

The performative is authoritative for message intent; payload prose cannot silently override it.

- `QUERY` — request information only.
- `REPORT` — provide state, evidence, or results.
- `REQUEST` — ask the target to consider an action.
- `EXECUTE` — request an explicitly scoped effect.
- `REVIEW` — request evaluation of an exact subject.
- `ACK` — acknowledge receipt/acceptance for processing.
- `REJECT` — refuse the message or requested action.
- `WAIT` — report a real unresolved dependency/frontier.
- `CONFLICT` — report incompatible state, evidence, subject, or operation semantics.
- `CANCEL` — request cancellation of an operation not irreversibly complete.
- `RECEIPT` — report verified result/effect state for a prior operation.

## Subject binding

`subject` names the logical object. `exact_subject` binds an immutable version/candidate. `REVIEW` requires an `exact_subject`. A mutating `EXECUTE` against a named subject also requires `exact_subject`.

Receivers must not substitute a newer or nearby subject and call it equivalent.

## Authority claims

`authority_claim_ref` points to externally established authority evidence. It is not authority itself. A mutating `EXECUTE` requires an authority reference, but receiver admission still independently determines whether that authority is valid for the exact action, target, scope, and effect.

## Effect classes

- `READ_ONLY`
- `REVERSIBLE_MUTATION`
- `PROTECTED_MUTATION`
- `IRREVERSIBLE`

A mutating `EXECUTE` requires `operation_id`, `idempotency_key`, `authority_claim_ref`, and exact-subject binding when a subject exists.

## Constraints and prohibitions

`constraints` are conditions that must remain true. `prohibited_effects` are hard negative boundaries. A receiver must not reinterpret a prohibition as a preference.

## Idempotency and duplicate operations

Packet identity and operation identity are distinct. The Intranel operation digest intentionally excludes relay/packet metadata such as `message_id`, `actor`, `reply_to`, and security profile.

If the same operation/idempotency identity reappears with the same operation semantics, the receiver returns `DUPLICATE` and does not re-execute it. If the same operation identity reappears with conflicting semantics or a different idempotency key, the result is `CONFLICT`.

## Receiver decisions

- `ALLOW` — required checks passed for this message/effect.
- `DUPLICATE` — same operation already exists; do not execute again.
- `REJECT` — known invalid/unsupported/unauthorized request.
- `QUARANTINE` — authentication, replay, authority, or integrity uncertainty makes action unsafe.
- `CONFLICT` — exact-subject or duplicate-operation semantics conflict.

Known failed authentication is `REJECT`; authentication uncertainty is `QUARANTINE`. Replay uncertainty is `QUARANTINE`. Exact-subject mismatch is `CONFLICT`. Invalid mutation authority is `REJECT`; unresolved authority is `QUARANTINE`.

## Canonical representation

V1 canonical form is UTF-8 JSON with sorted object keys, no insignificant whitespace, preserved array order, no non-finite numbers, and strict field parsing. The SHA-256 digest of canonical bytes is a content identity only. It is not a signature or authority proof.

## Security

Security profiles are defined separately in `SECURITY_PROFILES_V1.md`. Security profile selection never weakens authority checks.

## Versioning

Unsupported protocol versions fail closed. Unknown fields fail closed. Future extension must use a new defined field/version/capability instead of relying on receivers to guess intent.
