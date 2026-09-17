# Intranel V1 Protocol Design

Date: 2026-09-17
Status: historical approved design; superseded where amended by hostile-repair specification

This document records the original `INTRANEL/1` design. Independent hostile review of the first implementation later found trust-boundary defects. Do not treat this historical design as the current qualification source where it conflicts with:

- `docs/superpowers/specs/2026-09-17-intranel-v1-hostile-repair-amendment.md`;
- `spec/INTRANEL_1.md` (current normative protocol);
- exact repaired executable source `9cd1ba4d4da67c42bc9a186818c9229213b6c762`.

The durable design intent remains: machine-oriented coordination with deterministic semantics; distinct origin/actor/target/reply routing; packet identity distinct from logical operation identity; exact-subject binding; authority claims that never create authority by syntax/transport; idempotent mutation semantics; fail-closed receiver admission; canonical content identity; schema/vectors; security-profile and Bus transport boundaries; and no hidden chain-of-thought transport.

The hostile-repair amendment strengthens that intent with receiver-owned effect classification, exact-message-bound receiver evidence, immutable semantic JSON, constraint/prohibition evidence, real transport-security attestation, cancellation target/cancellability evidence, bound receipt claims, parser/schema parity, restricted cross-runtime numeric semantics, explicit resource limits, and completed-CANCEL retry idempotency.

Historical details remain available in Git history; current behavior and qualification must be read from the current normative spec, repaired source, tests, and exact-head review evidence.
