# Intranel V1 Hostile Rereview R2 Amendment

Date: 2026-09-17
Status: `R2_REPAIR_CANDIDATE / NOT_INDEPENDENTLY_REQUALIFIED / DRAFT`

Base repaired semantic subject: `92276664ab9dbe6adbe83b3c6f1e777e945b4965`.

This amendment records second-order defects found while independently rereviewing the first hostile-repair cut. It supersedes only the affected interoperability/correlation statements until the normative protocol text is consolidated. It does not authorize merge, deployment, installation, cryptographic trust, or production use.

## 1. String-length units

Draft 2020-12 `maxLength` counts Unicode code points. The first repair implementation instead enforced governance-scalar and JSON-string limits in UTF-8 bytes, which allowed the JSON Schema and Python parser to disagree for multibyte strings.

R2 therefore defines per-string limits in Unicode code points:

- address: 320 code points;
- token: 256 code points;
- governance scalar: 4096 code points;
- JSON string value: 8192 code points;
- JSON object key: 256 code points, additionally restricted to printable ASCII.

The whole canonical message limit remains 65,536 UTF-8 bytes. The byte-level whole-message ceiling remains the outer bound for multibyte content.

## 2. Timestamp syntax

`observed_at` and `expires_at` use the RFC 3339 `date-time` syntax represented by JSON Schema `format: date-time`, not the wider set of strings accepted by Python `datetime.fromisoformat`.

The reference parser therefore requires:

- full date;
- `T` or `t` date/time separator;
- hour, minute, and second;
- optional fractional seconds;
- `Z`/`z` or an explicit `±HH:MM` offset.

Python-only variants such as a space separator, reduced-precision time without seconds, or colonless offsets are not INTRANEL/1 timestamps even when `fromisoformat` can parse them.

The semantic ordering rule `expires_at > observed_at` remains a reference parser invariant. JSON Schema `format: date-time` validates each timestamp individually; Draft 2020-12 does not express the ordering relation between two sibling properties.

## 3. Schema/parser parity boundary

The JSON Schema is the structural wire validator for constraints representable in Draft 2020-12. The Python parser/reference admission implementation additionally enforces semantic and cross-field invariants that JSON Schema cannot faithfully express without custom keywords.

The project must therefore not claim universal parser/schema equivalence.

Shared parity tests must cover schema-expressible constraints such as:

- protocol/version and closed vocabularies;
- required/nullability rules;
- structural `EXECUTE`, `CANCEL`, and `RECEIPT` bindings;
- per-string and collection bounds expressible through standard keywords;
- RFC 3339 timestamp syntax;
- canonical numeric-domain restrictions represented in the schema;
- printable-ASCII object-key rules.

Reference semantic tests separately cover at least:

- `expires_at > observed_at`;
- whole canonical message byte limit;
- exact receiver-evidence binding;
- receiver-owned effect classification;
- cancellation request operation identity distinct from `target_operation_id`;
- cancellation state/cancellability evidence;
- duplicate-operation lookup completeness;
- duplicate-operation semantics and receipt/report correlation.

A test failure in either layer is a protocol qualification failure for its exact subject; schema acceptance alone never implies admission.

## 4. Operation correlation versus duplicate execution

`operation_id` is used both by operation-request messages and by correlation messages such as `RECEIPT` that identify the prior operation being reported.

Duplicate/idempotency execution semantics apply only to messages that themselves request an operation (`EXECUTE` and `CANCEL` in V1). A `RECEIPT` carrying the same `operation_id` as a completed operation is not a retry of that operation and must not be forced through the prior operation's idempotency key or operation-semantic digest comparison.

The receipt remains an unverified receipt claim until independently read back/verified; this change only prevents correlation identity from being mistaken for retry identity.

## 5. Cancellation operation identity

A `CANCEL` request is a distinct operation from the operation it targets. Consequently:

`CANCEL.operation_id != CANCEL.target_operation_id`

Equality is a semantic `CONFLICT`. The receiver must reject the self-target relation even if otherwise matching `CancellationEvidence` says the target is cancellable.

This cross-field inequality is enforced by the reference admission layer rather than pretended to be a standard Draft 2020-12 schema constraint.

## 6. Duplicate-lookup completeness

An operation-bearing request cannot distinguish "no prior operation exists" from "the receiver did not check" merely by receiving `prior_operation=None` as an implicit default. Treating those states as equivalent makes idempotency fail open.

For `EXECUTE` and `CANCEL` in the V1 reference API:

- omitted `prior_operation` means the duplicate lookup is unverified and yields `QUARANTINE`;
- explicit `prior_operation=None` means receiver-confirmed absence of a prior operation record and permits normal fresh-operation admission to continue;
- an `OperationRecord` means receiver-confirmed presence and triggers exact operation-id, idempotency-key, operation-digest, and completion-state checks;
- an `OperationRecord` for a different operation identity is `CONFLICT` rather than evidence of absence.

Correlation-only messages such as `RECEIPT` are not themselves operation requests and therefore do not require a duplicate-execution lookup solely because they carry the referenced operation's `operation_id`.

This distinction is a caller/receiver contract: explicit `None` must only be supplied after the receiver has established absence in its operation store. Intranel V1 does not itself provide a durable operation database.

## Qualification boundary

The R2 changes are second-order hostile repairs. Frozen regressions demonstrate the defects being targeted, but the R2 exact head still requires fresh complete verification and independent hostile rereview before any qualification state can advance.
