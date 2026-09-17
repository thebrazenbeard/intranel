# Intranel V1 Hostile Self-Review — 2026-09-17

Reviewed implementation subject: `2e0b4bf853b94e076afa70f16b86d62a7c0f4884`
Base `main`: `ad164ec7408e3f446dc183bf040af5480ad603f2`
Protocol: `INTRANEL/1`
Disposition: `SOURCE_REVIEW_SELF_PASS_WITH_EXPLICIT_V1_LIMITS`

This is a historical hostile self-review, not independent qualification. The review document was intentionally committed after the exact implementation subject above so it does not self-reference its own commit.

> **Supersession note — 2026-09-17:** This review does **not** describe the current repaired candidate. An independent hostile review of later subject `b7a8c08483a6f7cdce9323b39a83ef86e96e748f` found material trust-boundary defects and returned `FAIL / CHANGES REQUIRED`. Those findings drove the hostile-repair work. Current repaired executable source is `9cd1ba4d4da67c42bc9a186818c9229213b6c762`; do not carry this historical SELF_PASS forward as current qualification.

## Verification evidence

Fresh local verification against the historical V1 implementation content:

- `PYTHONPATH=src python -m unittest discover -s tests -v` -> **48 tests, 0 failures**.
- `python -m compileall -q src tests` -> exit 0.
- critical persisted production/test blobs were read back after write; production parser/admission semantics, vectors, protocol text and hostile tests correspond to the verified V1 subject. Formatting-only serialization differences in one test file and JSON Schema do not change their tested semantics.

No merge, deployment, production install, provider mutation, encryption-key creation, or Bus-topology mutation was performed.

## Hostile requirements

1. **PASS — origin/actor separation.** `test_relay_preserves_origin_while_actor_changes` proves relay actor and semantic origin remain distinct.
2. **PASS — unknown fields fail closed.** `test_unknown_field_is_rejected` rejects undeclared fields.
3. **PASS — unsupported protocol fails closed.** `test_unsupported_protocol_is_rejected` rejects non-`INTRANEL/1` versions.
4. **PASS — mutation authority binding required.** `test_mutating_execute_requires_authority_operation_and_idempotency` rejects mutating `EXECUTE` without `authority_claim_ref`.
5. **PASS — idempotency binding required.** The same test rejects missing `operation_id` and `idempotency_key` before mutation admission.
6. **PASS — exact-subject mismatch conflicts.** `test_exact_subject_mismatch_conflicts` returns `CONFLICT`. Malformed timestamp data fails parsing; replay/freshness uncertainty is separately `QUARANTINE` by design.
7. **PASS — authentication/replay uncertainty quarantines.** Dedicated authentication and replay tests return `QUARANTINE`; known failed actor authentication returns `REJECT`.
8. **PASS — invalid authority rejects.** `test_invalid_authority_rejects_mutating_execute` returns `REJECT`.
9. **PASS — completed duplicate does not re-execute.** Same operation/idempotency/semantic digest returns `DUPLICATE`.
10. **PASS — conflicting duplicate semantics conflict.** Same operation identity with changed operation semantics or idempotency key returns `CONFLICT`.
11. **PASS — canonical mapping key order is identity-neutral.** Canonical SHA-256 remains stable across mapping key order.
12. **PASS — semantic changes alter content identity.** Digest changes when semantic content changes.
13. **PASS — security profile does not grant authority.** `PRIVATE` and `SEALED` requests with invalid authority still return `REJECT`.
14. **PASS — relay does not transfer authority.** `test_relay_actor_does_not_inherit_origin_authority` rejects a relayed mutation when receiver-side authority validation fails.

## Additional hostile findings repaired before this historical review

- Governance-significant scalar fields previously accepted arbitrary Python values through the dataclass boundary. The parser restricted them to non-empty string-or-null where applicable.
- Payload and receipt values rejected non-JSON values, non-string object keys and non-finite numbers.
- `observed_at` and `expires_at` required offset-aware ISO 8601 values; naive/malformed timestamps failed parsing and expiry had to be later than observation when both were present.
- JSON Schema conditionals required non-null binding values for `REVIEW` and mutating `EXECUTE`, rather than merely requiring the key to exist.
- Duplicate-operation identity used an operation-semantic digest that excluded legitimate packet/relay metadata such as `message_id`, `actor`, `reply_to` and security profile.

## Deliberate historical V1 exclusions

The following were **not implemented and were not claimed**:

- production cryptography or key management;
- binary/compact wire encoding;
- live Bus parser/writer automation;
- production routing/cutover;
- installation into all Vera chats/lanes;
- automatic authority delegation;
- hidden chain-of-thought or private-reasoning transfer.

These are scope boundaries, not implied completion.

## Historical review conclusion

Within the historical subject `2e0b4bf8…`, this self-review recorded a source-local PASS. Later independent review invalidated any attempt to treat that PASS as current qualification. Current disposition must be read from the exact repaired subject and fresh rereview evidence, not from this file alone.
