# Intranel V1 Hostile Repair Plan

> This plan records the hostile-repair workstream for `INTRANEL/1`. It does not authorize merge, deployment, installation, cryptographic activation, provider mutation, or Bus-topology changes.

**Current repaired executable source subject:** `9cd1ba4d4da67c42bc9a186818c9229213b6c762`

**Current state:** source repairs implemented; 83-test reconstructed local behavioral suite plus compile verification GREEN under CPython 3.13.5; native CPython 3.12 and hosted-CI qualification unresolved; fresh independent hostile rereview required.

## Repair objectives

- remove sender-controlled effect-class authority bypass;
- bind receiver evidence to the exact message/operation/subject/authority claim;
- make semantic JSON state deeply immutable;
- enforce constraints/prohibitions at admission;
- require real transport-security evidence instead of trusting profile labels;
- distinguish cancellation request identity from target-operation identity and require cancellability evidence;
- bind receipt claims without treating them as self-verifying effect truth;
- enforce parser/schema parity through Draft 2020-12 validation;
- define a cross-runtime-safe canonical numeric subset;
- enforce untrusted-input resource bounds;
- preserve completed-operation idempotency for `CANCEL` retries without re-cancelling or requiring the old target to remain cancellable.

## Verification expectations

- regression first for every repaired behavior;
- full `unittest` discovery after repair;
- compile verification;
- exact source/head readback;
- independent hostile rereview bound to the repaired source SHA;
- hosted/native qualification reported separately from local behavioral verification.

## Qualification boundary

A local PASS is not independent qualification. Hosted runner provisioning failures before checkout/test do not count as source FAIL, but they also do not count as GREEN. The PR remains draft/unmerged until fresh review evidence supports a later integration decision and Patrick separately authorizes that effect.
