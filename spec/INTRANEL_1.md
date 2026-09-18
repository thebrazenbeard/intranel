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

Identity-token fields (`message_id`, operation IDs, `parent_message_id`, `conversation_id`, and `idempotency_key`) use 1-256 printable ASCII characters (`U+0021` through `U+007E`). Unicode text belongs in semantic scalar fields or JSON payload values, not in operation/correlation tokens.

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

A `CANCEL` request is itself an operation and therefore has its own `operation_id` and `idempotency_key`. `target_operation_id` names the distinct operation to cancel. The two identities must be distinct; `operation_id == target_operation_id` is a semantic `CONFLICT`.

`CANCEL` also requires `subject`, `exact_subject`, `authority_claim_ref`, and a non-`READ_ONLY` effect class. Receiver admission requires separate `CancellationEvidence` bound to the same `target_operation_id` and `exact_subject` for a not-yet-completed cancellation request:

- no cancellation evidence or unknown cancellability -> `QUARANTINE`;
- target/state mismatch -> `CONFLICT`;
- known non-cancellable/irreversibly-complete target -> `REJECT`;
- only known cancellable target state may proceed to the normal admission result.

A retry of the **same verified-complete cancellation operation** is different: after exact-message binding, authentication/replay, effect classification, transport security, exact-subject/constraint/prohibition checks, and authority validation succeed, an identical completed prior operation returns `DUPLICATE` without attempting to prove that its target is still cancellable. It must not re-execute or re-cancel the target.

## Receipt semantics

A `RECEIPT` message must bind `operation_id`, `exact_subject`, and a structured `receipt` object. This prevents an unbound success-looking object from masquerading as a receipt for an unspecified operation/state.

`RECEIPT` remains a **receipt claim**. `ALLOW` means the message may be accepted for processing under Intranel admission; it does not make the claimed effect verified. Effect truth still requires the appropriate independent target readback, provenance, or verification mechanism outside the receipt's own assertion.

A receipt may carry the same `operation_id` as the operation it reports, but that is correlation identity, not a request to execute that operation again. `RECEIPT` is therefore not subjected to `EXECUTE`/`CANCEL` duplicate-execution comparison merely because its `operation_id` matches an existing operation record.

## Time and freshness

`observed_at` and `expires_at`, when present, use RFC 3339 `date-time`, the offset-aware ISO 8601 profile represented by Draft 2020-12 JSON Schema: full date; `T` or `t`; hour, minute, and second; optional fractional seconds; and `Z`/`z` or an explicit `±HH:MM` offset. Python-only `datetime.fromisoformat` variants outside that syntax are not INTRANEL/1 timestamps. When both timestamps are present, `expires_at` must be later than `observed_at`.

Replay/freshness is receiver evidence. Unknown replay state is `QUARANTINE`; a known replay failure is `REJECT` in the V1 reference admission implementation.

## Idempotency and duplicate operations

Packet identity and operation identity are distinct. The Intranel operation digest intentionally excludes legitimate relay/packet metadata such as `message_id`, `actor`, `reply_to`, and security profile. It includes operation semantics such as `target_operation_id`, exact subject, payload, authority reference, constraints, prohibitions, effect class, capabilities, and provenance.

If the same operation/idempotency identity reappears with the same operation semantics and the prior operation is verified complete, the receiver returns `DUPLICATE` and does not re-execute it. If it is known but incomplete, the result is `QUARANTINE`. Conflicting semantics or a different idempotency key produce `CONFLICT`. For mutating operations, duplicate recognition happens only after the current message passes the receiver's trust/authority boundary; it is not an authority bypass or an unauthenticated operation-existence oracle.

For `EXECUTE`, `operation_id` and `idempotency_key` are paired identity fields: either both are absent/null for a read-only execution with no retry identity, or both are present as tokens. A read-only `EXECUTE` may therefore be operation-bound, but it cannot carry an unrecordable half-identity.

For an `EXECUTE` or `CANCEL` that carries an `operation_id`, operation-store lookup is explicit receiver evidence: omitting the `prior_operation` lookup result means the lookup is unresolved and yields `QUARANTINE`; explicit `None` means the receiver checked and found no prior record; an `OperationRecord` means presence was established and exact operation identity, idempotency key, semantic digest, and completion state are checked. A read-only `EXECUTE` with no `operation_id` has no duplicate-operation identity to look up.

Because `admit()` is a pure decision function, lookup alone does not guarantee at-most-once execution under concurrency. Before dispatching any operation-bearing effect after `ALLOW`, the receiver must atomically reserve that `operation_id`/idempotency identity in its operation store (or use an equivalent compare-and-set transaction) so two concurrent first-seen requests cannot both execute. Intranel V1 does not itself provide the durable operation store or transaction mechanism.

## Receiver decisions

- `ALLOW` — the modeled required checks passed for this exact message/effect. It is not a statement that every downstream domain invariant has been proven.
- `DUPLICATE` — the same operation is already verified complete; do not execute it again.
- `REJECT` — known invalid, unsupported, unauthorized, unsafe, or non-cancellable request.
- `QUARANTINE` — required authentication, replay, authority, effect, constraint, transport, cancellation, or integrity evidence is unresolved.
- `CONFLICT` — message/evidence binding, exact-subject, effect-class, cancellation-target, or duplicate-operation semantics conflict.

## Immutable semantic state

Parsed payload and receipt data are recursively copied and frozen before the message can be used. Mutating the caller's original Python objects after parsing cannot alter the message or its digest. `to_mapping()` returns a fresh deep mutable copy and likewise cannot mutate the validated internal state.

## Raw wire JSON boundary

A raw wire message is UTF-8 JSON text. The reference `parse_json_message()` boundary applies before schema and semantic parsing:

- raw UTF-8 input is limited to 65536 bytes before JSON decode;
- invalid UTF-8 is rejected;
- duplicate JSON object members are rejected at every nesting level before they can collapse into a mapping;
- non-standard JSON constants such as `NaN`, `Infinity`, and `-Infinity` are rejected;
- the decoded top-level value must be a JSON object;
- hostile nesting that exceeds the runtime JSON decoder's safe recursion boundary fails closed through the Intranel validation error boundary;
- only after those checks does V1 apply structural/schema and semantic message validation.

Duplicate JSON object member handling is therefore not implementation-defined in INTRANEL/1. A transport or implementation that does not call the reference helper must enforce equivalent raw-wire rules before schema validation or `parse_message()`.

## Semantic default normalization

Canonical message identity is computed from the parsed, **default-normalized semantic form**, not from the raw JSON object exactly as received. Missing and explicit defaults therefore describe the same semantic message and produce the same canonical bytes/content digest.

For a syntactically valid V1 message, omitted optional fields normalize as follows before canonical serialization:

- `operation_id`, `target_operation_id`, `parent_message_id`, `subject`, `exact_subject`, `authority_claim_ref`, `expected_response`, `observed_at`, `expires_at`, `idempotency_key`, `status`, `error`, and `receipt` -> `null`;
- `payload` -> `null`;
- `constraints`, `prohibited_effects`, `capabilities`, and `provenance` -> `[]`;
- `ack_required` -> `false`;
- `priority` -> `3`.

The required wire fields `protocol`, `origin`, `actor`, `target`, `reply_to`, `message_id`, `conversation_id`, `performative`, `effect_class`, and `security_profile` do not have omission defaults and must be present.

Independent implementations must apply these semantic defaults before computing canonical message bytes or message content identity. Hashing a schema-valid raw object before default normalization is not INTRANEL/1 canonical message hashing.

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

V1 validates bounded untrusted semantic values before canonicalization/use. Per-string limits use Unicode code points so they are directly representable by Draft 2020-12 `maxLength`; the canonical whole-message limit remains byte-based:

- address length: 320 Unicode code points;
- identity tokens: 1-256 printable ASCII code points (`U+0021` through `U+007E`);
- governance scalar strings: 4096 Unicode code points;
- string-list fields: at most 64 items;
- JSON object/array: at most 256 direct items;
- JSON nesting depth: at most 24;
- total JSON semantic nodes: at most 4096;
- JSON string values: at most 8192 Unicode code points;
- JSON object keys: at most 256 Unicode code points and printable ASCII;
- canonical whole message: at most 65536 bytes of UTF-8.

The whole-message byte bound remains the outer transport/resource ceiling for multibyte Unicode content. These are V1 interoperability/safety bounds, not claims of denial-of-service immunity for every surrounding transport/runtime.

## Schema and reference-semantics boundary

`schema/INTRANEL_MESSAGE_V1.schema.json` is Draft 2020-12 and is the structural wire validator for constraints expressible with standard schema keywords. Shared parity tests cover that expressible surface, including protocol/version vocabularies, required/nullability rules, structural `EXECUTE`/`CANCEL`/`RECEIPT` bindings, RFC 3339 timestamp syntax, numeric-domain restrictions, per-string/collection bounds, and printable-ASCII object-key rules.

The reference parser/admission layer additionally enforces semantic or cross-field invariants that standard Draft 2020-12 does not faithfully express here, including full Gregorian calendar validity for timestamps (for example rejecting February 30 even when a standard schema format checker accepts it), `expires_at > observed_at`, the 65,536-byte canonical whole-message ceiling, exact receiver-evidence binding, receiver-owned effect classification, cancellation self-target inequality and cancellability state, and operation-store lookup completeness. Schema acceptance alone never implies parser or receiver admission.

## Versioning

Unsupported protocol versions fail closed. Unknown fields fail closed. Future extension must use a new defined field/version/capability instead of relying on receivers to guess intent.
