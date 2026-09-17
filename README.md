# Intranel

Intranel is Vera's machine-oriented internal coordination protocol family. The current protocol is `INTRANEL/1`.

It exists to reduce ambiguity in chat-to-chat, lane-to-lane, reviewer, relay, and infrastructure coordination by separating message intent, identity, operation correlation, exact subject, authority claims, constraints, effect class, security profile, and receipts into deterministic fields.

Intranel is **not a chain-of-thought transport**. It is **not an authority source**. It is not a claim of shared consciousness or hidden process continuity. It carries explicit coordination data that receivers must validate independently.

## V1 contains

- strict `INTRANEL/1` message parsing and Draft 2020-12 schema parity tests;
- namespaced addressing with distinct `origin`, `actor`, `target`, and `reply_to`;
- closed performative/effect/security vocabularies;
- packet identity separate from logical operation and cancellation-target identity;
- receiver evidence bound to exact message/operation identity;
- receiver-owned effect classification before mutation authority checks;
- hard constraint/prohibition and transport-security admission evidence;
- deep-immutable payload/receipt semantic state;
- bounded canonical UTF-8 JSON and SHA-256 content identity;
- relay-safe operation-semantic digests and fail-closed duplicate handling;
- cancellation state/cancellability evidence;
- receipt claims bound to prior operation/state without self-verifying their effect;
- frozen interoperability vectors;
- security-profile and Chat Communication Bus transport specifications.

## V1 deliberately does not contain

- production deployment/cutover;
- encryption or key-management implementation;
- binary wire encoding;
- automatic authority delegation;
- automatic proof that a receipt's claimed effect is true;
- hidden reasoning transfer.

## Verify locally

```bash
python -m pip install -e ".[test]"
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```

See `spec/INTRANEL_1.md` for normative semantics and `docs/superpowers/specs/2026-09-17-intranel-v1-design.md` for the architecture rationale.
