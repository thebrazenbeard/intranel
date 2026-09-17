# Intranel V1 Hostile Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair every independent hostile-review finding on Intranel PR #1 while preserving `INTRANEL/1`'s fail-closed authority boundary and keeping the PR draft/unmerged.

**Architecture:** Keep sender declarations descriptive and receiver admission authoritative. Bind all receiver evidence to the exact message/operation, deep-freeze semantic JSON state, make constraints/security/cancellation explicit admission evidence, converge parser and JSON Schema on one corpus, and narrow canonical JSON to an explicitly cross-runtime-safe subset rather than inventing a proprietary number serializer.

**Tech Stack:** Python 3.12 standard library runtime, `unittest`, JSON Schema Draft 2020-12 validation in test-only tooling, Markdown protocol specs.

**Spec:** `spec/INTRANEL_1.md` plus independent hostile review on PR #1 exact subject `b7a8c08483a6f7cdce9323b39a83ef86e96e748f`.

## Global Constraints

- Sender-declared `effect_class` never decides whether mutation controls apply.
- Receiver evidence must be cryptographically/content-identity bindable to the exact message/operation even though V1 does not implement transport cryptography.
- `ALLOW` must not imply unchecked constraints, prohibitions, transport protection, or cancellation state.
- Runtime remains fail-closed on unknown/ambiguous governance state.
- No merge, deployment, installation, key-management, provider mutation, or Bus topology mutation.
- PR #1 remains draft.

---

### Task 1: Bound receiver admission and receiver-computed effect class

**Files:**
- Modify: `src/intranel/admission.py`
- Modify: `src/intranel/__init__.py`
- Modify: `tests/test_admission.py`
- Modify: `tests/test_hardening.py`

**Interfaces:**
- Produce bound `ReceiverEvidence`/equivalent containing exact message/operation bindings and receiver-computed `effective_effect_class`.
- `admit()` fails closed on binding mismatch or unknown effect classification.

- [ ] Write failing regressions for effect-class underdeclaration and stale/cross-message receiver evidence.
- [ ] Verify RED.
- [ ] Implement exact binding validation and receiver-computed effect enforcement.
- [ ] Verify GREEN.

### Task 2: Deep immutable semantic state

**Files:**
- Modify: `src/intranel/message.py`
- Modify: `src/intranel/canonical.py`
- Modify: `tests/test_hardening.py`

**Interfaces:**
- Parsed/directly-constructed payload and receipt state cannot be mutated through source objects or `to_mapping()` outputs.

- [ ] Write failing TOCTOU regressions.
- [ ] Verify RED.
- [ ] Deep-freeze internal JSON and deep-thaw outbound mappings.
- [ ] Verify GREEN.

### Task 3: Constraints, security profile, and cancellation evidence

**Files:**
- Modify: `src/intranel/admission.py`
- Modify: `src/intranel/message.py`
- Modify: `schema/INTRANEL_MESSAGE_V1.schema.json`
- Modify: `tests/test_admission.py`
- Modify: `tests/test_hardening.py`

**Interfaces:**
- Non-empty constraints/prohibitions require bound receiver evaluation.
- Security profile requires receiver transport attestation.
- `CANCEL` binds a distinct target operation and exact cancellability evidence.

- [ ] Write failing regressions for unchecked constraints/prohibitions, plaintext `SEALED`, and unknown/irreversible cancellation target state.
- [ ] Verify RED.
- [ ] Implement bound evidence and target-operation semantics.
- [ ] Verify GREEN.

### Task 4: Parser/schema convergence and shared corpus

**Files:**
- Modify: `schema/INTRANEL_MESSAGE_V1.schema.json`
- Modify: `tests/test_vectors.py`
- Modify: `pyproject.toml`
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Parser and Draft 2020-12 schema accept/reject the same frozen valid/invalid corpus.

- [ ] Write shared schema/parser corpus tests.
- [ ] Verify RED on known divergence.
- [ ] Align mutating `EXECUTE` and `CANCEL` requirements.
- [ ] Verify GREEN.

### Task 5: Cross-runtime canonical subset, receipt honesty, and resource bounds

**Files:**
- Modify: `src/intranel/canonical.py`
- Modify: `src/intranel/message.py`
- Modify: `spec/INTRANEL_1.md`
- Modify: `spec/SECURITY_PROFILES_V1.md`
- Modify: `README.md`
- Modify: `tests/test_canonical.py`
- Modify: `tests/test_message.py`
- Modify: `tests/test_docs_contract.py`
- Modify: `vectors/README.md`
- Modify/add vectors as needed.

**Interfaces:**
- V1 canonical numeric domain is a documented RFC-8785-compatible safe subset: finite safe integers only; floats/negative-zero/exponent forms are not accepted semantic values.
- `RECEIPT` is an unverified receipt claim unless separately admitted/verified and is bound to a prior operation.
- Identifier/string/depth/collection/message-size limits are explicit and enforced before untrusted canonicalization.

- [ ] Write failing canonical/receipt/resource-limit regressions.
- [ ] Verify RED.
- [ ] Implement the narrowed canonical domain, receipt binding, and limits.
- [ ] Verify GREEN.

### Task 6: Exact-head verification and hostile rereview request

**Files:**
- Update: PR #1 body/status commentary
- Add: a new repair verification note under `docs/reviews/`
- Mirror status to `chat-communication-bus`.

- [ ] Run fresh full unit suite and compile check on the exact repaired source.
- [ ] Read back exact remote blobs/tree/head and reconcile drift.
- [ ] Record which hostile findings are repaired and which remain non-claims.
- [ ] Update the draft PR without merging or marking ready.
- [ ] Request fresh independent hostile rereview of the new exact head and mirror that frontier to the Bus.
