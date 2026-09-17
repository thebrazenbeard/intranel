# INTRANEL/1

`INTRANEL/1` is the first semantic protocol for communication inside the Vera intranel network. It is designed for machine coordination among Vera chats/lanes and other explicitly addressed infrastructure without relying on natural-language implication for governance-significant meaning.

## Core rule

A syntactically valid Intranel message is data, not permission. **Transport does not grant authority.** Authentication, confidentiality, routing, possession of a protocol implementation, or receipt over a trusted transport does not by itself authorize the requested effect.

A receiver must independently establish evidence for the exact message it is considering. That receiver evidence is bound to the message content digest, operation digest when present, `origin`, `actor`, `target`, `exact_subject`, and `authority_claim_ref`. Reusing evidence created for another message is `CONFLICT`.

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
- `operation_id`: one logical requested operation across retry/relay;
- `target_operation_id`: for `CANCEL`, the distinct operation whose cancellation is requested;
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
- `CANCEL` — request cancellation of a distinct operation that is still cancellable.
- `RECEIPT` — carry a receipt claim about a prior operation; receipt content is not effect truth until independently verified/read back.

## Subject binding

`subject` names the logical object. `exact_subject` binds an immutable version/candidate/state subject. `REVIEW` requires `exact_subject`.

Every mutating `EXECUTE` requires `operation_id`, `idempotency_key`, `authority_claim_ref`, and `exact_subject`, even when the human-readable `subject` field is omitted. A receiver must not silently substitute a newer or nearby subject.

## Receiver evidence and effect classification

Sender-declared `effect_class` is a claim about the requested effect, not the receiver's authority decision.

For `EXECUTE` and `CANCEL`, the receiver must independently classify the effective action through receiver-owned handler/action metadata and bind that classification into `ReceiverEvidence.effective_effect_class`. It must **not** derive that value by trusting the message's `effect_class` or free-form payload text.

- unknown receiver effect classification -> `QUARANTINE`;
- receiver/sender effect-class mismatch -> `CONFLICT`;
- known matching mutation classification -> mutation authority checks apply;
- a sender cannot bypass mutation controls by declaring `READ_ONLY` for an action the receiver classifies as mutating.

`ReceiverEvidence` is exact-message evidence, not a reusable bag of booleans. Its content and operation digest bindings prevent cross-message/stale-check reuse from falling through to `ALLOW`.

## Authority claims

`authority_claim_ref` points to externally established authority evidence. It is not authority itself. A mutating `EXECUTE` and every `CANCEL` require an authority reference, but receiver admission independently determines whether that authority is valid for the exact action, target, scope, and receiver-computed effect.

## Effect classes

- `READ_ONLY`
- `REVERSIBLE_MUTATION`
- `PROTECTED_MUTATION`
- `IRREVERSIBLE`

The wire value and receiver-owned effective classification must agree before `EXECUTE` or `CANCEL` can be admitted.

## Constraints and prohibitions

`constraints` are conditions that must remain true. `prohibited_effects` are hard negative boundaries. A receiver must not reinterpret a prohibition as a preference.

If either collection is non-empty, receiver admission requires bound evaluation evidence:

- unknown constraint satisfaction -> `QUARANTINE`;
- known unsatisfied constraint -> `REJECT`;
- unknown prohibited-effect clearance -> `QUARANTINE`;
- known prohibited effect would occur -> `REJECT`.

An `ALLOW` decision therefore never means "constraints were ignored."

## Security-profile attestation

The message `security_profile` is descriptive/requested protocol state; it cannot prove its own transport protection. Receiver admission requires `transport_security_satisfied` evidence bound to the exact message.

For `OPEN`, this means the transport's required endpoint-authentication/integrity posture is established and plaintext is acceptable for the message. For `PRIVATE` and `SEALED`, the applicable transport profile must independently establish the required confidentiality and authentication properties. False is `REJECT`; unresolved is `QUARANTINE`.

See `SECURITY_PROFILES_V1.md` for profile semantics. V1 still does not implement cryptography or key management.

## Cancellation

A `CANCEL` request is itself an operation and therefore has its own `operation_id` and `idempotency_key`. `target_operation_id` names the distinct operation to cancel.

`CANCEL` also requires `subject`, `exact_subject`, `authority_claim_ref`, and a non-`READ_ONLY` effect class. Receiver admission requires separate `CancellationEvidence` bound to the same `target_operation_id` and `exact_subject`:

- no cancellation evidence or unknown cancellability -> `QUARANTINE`;
- target/state mismatch -> `CONFLICT`;
- known non-cancellable/irreversibly-complete target -> `REJECT`;
- only known cancellable target state may proceed to the normal admission result.

## Receipt semantics

A `RECEIPT` message must bind `operation_id`, `exact_subject`, and a structured `receipt` object. This prevents an unbound success-looking object from masquerading as a receipt for an unspecified operation/state.

`RECEIPT` remains a **receipt claim**. `ALLOW` means the message may be accepted for processing under Intranel admission; it does not make the claimed effect verified. Effect truth still requires the appropriate independent target readback, provenance, or verification mechanism outside the receipt's own assertion.

## Time and freshness

`observed_at` and `expires_at`, when present, are offset-aware ISO 8601 timestamps. Naive timestamps are invalid. When both are present, `expires_at` must be later than `observed_at`.

Replay/freshness is receiver evidence. Unknown replay state is `QUARANTINE`; a known replay failure is `REJECT` in the V1 reference admission implementation.

## Idempotency and duplicate operations

Packet identity and operation identity are distinct. The Intranel operation digest intentionally excludes legitimate relay/packet metadata such as `message_id`, `actor`, `reply_to`, and security profile. It includes operation semantics such as `target_operation_id`, exact subject, payload, authority reference, constraints, prohibitions, effect class, capabilities, and provenance.

If the same operation/idempotency identity reappears with the same operation semantics and the prior operation is verified complete, the receiver returns `DUPLICATE` and does not re-execute it. If it is known but incomplete, the result is `QUARANTINE`. Conflicting semantics or a different idempotency key produce `CONFLICT`.

## Receiver decisions

- `ALLOW` — the modeled required checks passed for this exact message/effect. It is not a statement that every downstream domain invariant has been proven.
- `DUPLICATE` — the same operation is already verified complete; do not execute it again.
- `REJECT` — known invalid, unsupported, unauthorized, unsafe, or non-cancellable request.
- `QUARANTINE` — required authentication, replay, authority, effect, constraint, transport, cancellation, or integrity evidence is unresolved.
- `CONFLICT` — message/evidence binding, exact-subject, effect-class, cancellation-target, or duplicate-operation semantics conflict.

## Immutable semantic state

Parsed payload and receipt data are recursively copied and frozen before the message can be used. Mutating the caller's original Python objects after parsing cannot alter the message or its digest. `to_mapping()` returns a fresh deep mutable copy and likewise cannot mutate the validated internal state.

## Canonical representation

V1 canonical form is a deliberately restricted RFC-8785-compatible JSON subset so independent runtimes do not have to reproduce Python-specific floating-point serialization.

Canonical values use:

- UTF-8 JSON;
- sorted printable-ASCII object keys;
- no insignificant whitespace;
- preserved array order;
- JSON `null`/booleans;
- safe integral numeric values in `[-9007199254740991, 9007199254740991]`;
- integral float inputs normalized to integer form (`1.0` -> `1`, `-0.0` -> `0`);
- no non-integral floats, NaN, or infinities;
- UTF-8 string values with invalid Unicode rejected.

The SHA-256 digest of canonical bytes is content identity only. It is not a signature, authentication proof, or authority proof.

## Resource bounds

V1 validates bounded untrusted semantic values before canonicalization/use:

- address length: 320 characters;
- token length: 256 characters;
- governance scalar strings: 4096 UTF-8 bytes;
- string-list fields: at most 64 items;
- JSON object/array: at most 256 direct items;
- JSON nesting depth: at most 24;
- total JSON semantic nodes: at most 4096;
- JSON string values: at most 8192 UTF-8 bytes;
- JSON object keys: at most 256 UTF-8 bytes and printable ASCII;
- canonical whole message: at most 65536 bytes.

These are V1 interoperability/safety bounds, not claims of denial-of-service immunity for every surrounding transport/runtime.

## Schema and parser parity

`schema/INTRANEL_MESSAGE_V1.schema.json` is Draft 2020-12. The test suite validates a shared valid/invalid corpus through both the Python parser and a real Draft 2020-12 validator so mutating `EXECUTE`, `CANCEL`, `RECEIPT`, exact-subject, numeric-domain, and object-key rules cannot silently diverge.

## Versioning

Unsupported protocol versions fail closed. Unknown fields fail closed. Future extension must use a new defined field/version/capability instead of relying on receivers to guess intent.
