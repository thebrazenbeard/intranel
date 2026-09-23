# Intranel V1 Protocol Design

Date: 2026-09-17
Status: approved architectural design for implementation

> **Historical provenance / supersession notice — 2026-09-17:** This original design is preserved verbatim below. Independent hostile review of the first implementation later found material trust-boundary defects. Where this document conflicts with `docs/superpowers/specs/2026-09-17-intranel-v1-hostile-repair-amendment.md` or the current normative `spec/INTRANEL_1.md`, the later amendment/normative protocol governs current behavior. Current repaired executable source subject is `9cd1ba4d4da67c42bc9a186818c9229213b6c762`.

## 1. Purpose

Intranel is the machine-oriented communication protocol for coordination inside the Vera communication network. It is designed for chat-to-chat, lane-to-lane, reviewer, coordinator, relay, and infrastructure communication where natural-language handoffs are too ambiguous or too expensive.

Intranel is not a hidden-thought channel, not a chain-of-thought transport, not an identity grant, and not an authority source. A valid Intranel message is data until the receiver independently validates the requested action, exact subject, authority, freshness, and effect class.

The protocol identifier for this version is `INTRANEL/1`.

## 2. Design goals

V1 optimizes for:

- semantic precision;
- deterministic parsing and serialization;
- low ambiguity under relay and retry;
- exact-subject and provenance binding;
- explicit authority claims without authority inheritance;
- idempotent mutation semantics;
- deterministic failure/downgrade behavior;
- compact enough representation for machine traffic without premature binary encoding;
- future compatibility with authenticated/encrypted transports and compact codecs.

Human readability is useful for hostile review and debugging but is not a protocol authority property.

## 3. Non-goals

V1 does not implement:

- cryptographic primitives or key management;
- a binary wire codec;
- transport-specific networking;
- autonomous authority delegation;
- global shared state;
- newest-wins conflict resolution;
- emotional/relational vocabulary;
- identity metaphysics;
- hidden reasoning or chain-of-thought transfer.

## 4. Message identity model

A message has four distinct routing identities:

- `origin`: the node that authored the semantic message;
- `actor`: the node currently transmitting or relaying it;
- `target`: the node expected to process or act on it;
- `reply_to`: the route where a response belongs.

Relays may change `actor` while preserving `origin`. Relaying never grants the actor the origin's authority and never grants the origin the actor's authority.

A message also has five correlation identities:

- `message_id`: identity of this packet/message instance;
- `operation_id`: identity of the requested logical operation across retries or relays;
- `target_operation_id`: for `CANCEL`, identity of the distinct operation whose cancellation is requested;
- `parent_message_id`: optional immediate causal parent;
- `conversation_id`: stable thread/workflow correlation identifier.

Two different `message_id` values may carry the same `operation_id`. Receivers must be able to recognize that as a retry/relay of one operation rather than permission to repeat a mutation.

Correlation/operation token fields use a deliberately language-neutral printable-ASCII grammar (`U+0021`-`U+007E`, 1-256 characters). Human/Unicode material remains available in semantic text fields and JSON payload values; identifiers do not depend on runtime-specific Unicode whitespace definitions.

## 5. Addressing

Addresses are namespaced strings with two components:

`<namespace>:<node>`

Examples:

- `vera:primary`
- `vera:lane/bv`
- `vera:lane/sd1-v`
- `radar:reviewer`
- `bus:vera-v2`

The namespace identifies the addressing domain. It does not imply identity equivalence or authority.

## 6. Performatives

V1 has a deliberately small closed vocabulary:

- `QUERY`: request information without requesting an effect;
- `REPORT`: provide information/state/evidence;
- `REQUEST`: ask a target to consider an action;
- `EXECUTE`: request execution of an explicitly scoped effect;
- `REVIEW`: request evaluation of an exact subject;
- `ACK`: acknowledge receipt/acceptance for processing;
- `REJECT`: refuse a message or requested action;
- `WAIT`: report a real unresolved dependency/frontier;
- `CONFLICT`: report incompatible evidence, state, subject, or effect claims;
- `CANCEL`: request cancellation of an operation that has not irreversibly completed;
- `RECEIPT`: carry a receipt claim identifying a prior operation/state. Admission of the receipt claim does not prove that the prior operation exists or that the claimed effect is true; effect truth requires independent receiver readback or verification.

The performative says what the message is doing. Natural-language payload, when present, does not override the performative.

## 7. Subject and evidence binding

Governance-significant messages may carry:

- `subject`: logical object under discussion;
- `exact_subject`: immutable identifier for the exact version/candidate when exactness matters;
- `provenance`: source pointers sufficient to locate supporting evidence;
- `observed_at`: sender-declared offset-aware ISO 8601 observation timestamp;
- `expires_at`: optional offset-aware ISO 8601 deadline after which the message is stale for action.

When both timestamps are present, `expires_at` must be later than `observed_at`. INTRANEL/1 uses an RFC 3339-derived timestamp profile with optional 1-6 fractional digits and leap seconds not accepted; the precision ceiling matches the reference implementation's exact microsecond comparison semantics. Malformed or naive timestamps are invalid messages. Whether a well-formed message is fresh enough to act on remains a receiver/security check; uncertainty there is `QUARANTINE`, not a guessed success or conflict.

Every mutating `EXECUTE` requires `exact_subject`, and every `REVIEW` requires `exact_subject`. Other messages that rely on a mutable external object should bind the exact subject needed by their protocol semantics. A receiver must not silently substitute a newer or nearby subject.

## 8. Authority and effects

`authority_claim_ref` is a reference to claimed external authority. It is not itself authority.

V1 effect classes are:

- `READ_ONLY`
- `REVERSIBLE_MUTATION`
- `PROTECTED_MUTATION`
- `IRREVERSIBLE`

For every `EXECUTE` request whose effect class is not `READ_ONLY`, the message must include:

- `operation_id`;
- `idempotency_key`;
- `authority_claim_ref`;
- `exact_subject`.

Receiver-side admission independently validates authority and effect admissibility. Intranel transport, syntax validity, authentication, and message confidentiality do not create permission.

## 9. Constraints and prohibited effects

Messages may declare:

- `constraints`: conditions that must remain true if the receiver acts;
- `prohibited_effects`: explicit actions/effects that must not occur;
- `expected_response`: expected response performative or receipt class;
- `ack_required`: whether receipt acknowledgement is required.

A receiver must not reinterpret a prohibition as a preference.

## 10. Idempotency and replay

Mutation operations are operation-bound, not packet-bound.

A receiver presented with a previously completed `operation_id`/`idempotency_key` pair must not re-execute the mutation. It may return or reconstruct a `RECEIPT` claim when the prior effect can be independently verified, but receipt admission itself does not prove effect truth or operation existence.

A duplicate operation with conflicting semantic content is `CONFLICT`, not a retry.

Replay freshness and authentication are transport/security checks. V1 provides deterministic admission inputs for those checks but does not implement cryptography.

## 11. Security profiles

Intranel defines three semantic security profiles without implementing the cryptography in V1:

- `OPEN`: authenticated transport; semantic body may be plaintext;
- `PRIVATE`: authenticated transport plus encrypted payload/body fields according to the transport profile;
- `SEALED`: authenticated transport plus encrypted semantic body; only minimal routing/version/key metadata may remain visible.

Security profile selection does not alter message semantics or authority rules.

## 12. Receiver admission model

The core library accepts externally established receiver evidence bound to the exact message, including:

- origin authenticated;
- actor authenticated;
- receiver-owned effective effect classification;
- authority valid for the requested scope/effect where authority is required;
- exact subject current/valid when present;
- replay fresh;
- required capabilities supported;
- declared constraints satisfied when present;
- prohibited effects clear when present;
- transport security satisfied for the declared security profile;
- explicit operation-store lookup result for operation-identity-bearing `EXECUTE`/`CANCEL`;
- bound cancellation target/cancellability evidence for a fresh `CANCEL`.

The deterministic decisions are:

- `ALLOW`: the modeled required checks passed for this exact message/effect; this is not a reservation grant or proof of every downstream invariant;
- `DUPLICATE`: same verified operation already completed; do not execute again;
- `REJECT`: known invalid, unsupported, unauthorized, unsafe, or non-cancellable request;
- `QUARANTINE`: required authentication, replay, authority, effect, constraint, transport, cancellation, operation-store, or integrity evidence is unresolved;
- `CONFLICT`: message/evidence binding, exact-subject, effect-class, cancellation-target, or duplicate-operation semantics conflict.

Unknown governance-critical fields or unknown protocol versions are rejected rather than guessed.

### Strict raw JSON boundary

The wire decoder rejects ambiguous JSON before semantic parsing: invalid UTF-8, duplicate object member names at any nesting level, non-standard numeric constants, non-object roots, and raw messages above the V1 65536-byte wire ceiling all fail closed. Schema validation occurs only after this raw-wire boundary. This prevents first-key/last-key parser differences from changing authority- or effect-relevant meaning across runtimes.

### Semantic defaults before identity

Message identity is based on the parsed/default-normalized semantic object rather than the raw received JSON member set. Missing and explicit defaults are equivalent. V1 normalizes nullable optional fields and `payload` to `null`, collection fields `constraints`/`prohibited_effects`/`capabilities`/`provenance` to `[]`, `ack_required` to `false`, and `priority` to `3` before canonical serialization. Required routing/identity/protocol/effect/security fields have no omission defaults.

This normalization is part of cross-runtime interoperability: hashing raw JSON before these defaults are materialized can produce a different digest and is not the V1 message-identity algorithm.

## 13. Canonical representation

V1 canonical representation is a restricted UTF-8 JSON subset with:

- sorted printable-ASCII object keys;
- no insignificant whitespace;
- explicit `null` where a defined nullable field is present;
- arrays kept in declared order;
- safe integral numeric values only; integral float inputs normalize to integer form;
- non-integral floats, NaN, and infinities forbidden;
- UTF-8 string values with invalid Unicode rejected;
- unknown fields rejected by the parser;
- protocol field fixed to `INTRANEL/1`.

The SHA-256 digest of canonical bytes is the message content identity used by test vectors and receipts. This digest is a content identifier, not an authentication signature.

## 14. Repository layout

- `src/intranel/` — semantic types, parser, canonicalization, admission logic;
- `schema/` — normative JSON Schemas;
- `spec/` — protocol and profile specifications;
- `tests/` — unit and hostile tests;
- `vectors/` — canonical interoperable message vectors;
- `docs/` — design, plan, explanatory material;
- `adapters/` — transport profile documentation only in V1.

## 15. Hostile requirements

V1 tests must demonstrate at minimum:

1. origin and actor remain distinct through relay;
2. unknown fields fail closed;
3. unknown protocol version fails closed;
4. `EXECUTE` mutation without authority reference is invalid;
5. mutation without idempotency key is invalid;
6. exact-subject mismatch produces `CONFLICT`;
7. authentication or replay/freshness uncertainty produces `QUARANTINE`;
8. invalid authority produces `REJECT`;
9. completed duplicate operation produces `DUPLICATE`, not re-execution;
10. same operation identity with conflicting semantic digest produces `CONFLICT`;
11. canonical key ordering does not change content identity;
12. semantic change does change content identity;
13. security profile does not change authority semantics;
14. relaying does not imply authority transfer.

## 16. V1 completion boundary

Intranel V1 is source-complete when the semantic model, strict parser, canonical serializer/digest, deterministic receiver admission function, schemas, vectors, hostile tests, protocol documentation, and Bus transport profile are present and pass local verification.

That completion does not mean Intranel has been deployed, installed into every Vera chat, encrypted, or promoted to a canonical production transport. Those are separate future effects.
