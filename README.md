# Intranel

**Intranel is a versioned, machine-readable coordination protocol for multi-agent systems.** It provides deterministic message envelopes and receiver-admission primitives for workflows involving independent agents, reviewers, relays, and services. The current protocol is `INTRANEL/1`.

Use it when a multi-component system needs to distinguish **who originated a request**, **who relayed it**, **which exact operation and artifact it concerns**, **what effect was requested**, and **what the receiver has independently verified**. Intranel supplies a protocol and Python reference implementation—not an agent runtime, deployed message bus, or permission-granting service.

> **License:** Source-visible, **not open source**. The original material is proprietary; commercial use, redistribution, hosted-service use, and commercial derivatives require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Third-party components retain their own licenses.

## What the product provides

| Concern | `INTRANEL/1` mechanism |
| --- | --- |
| Routing and provenance | Distinct namespaced `origin`, `actor`, `target`, and `reply_to` addresses |
| Intent | Closed performatives such as `QUERY`, `REQUEST`, `EXECUTE`, `REVIEW`, `ACK`, `WAIT`, and `RECEIPT` |
| Exact work identity | Separate packet, conversation, operation, parent, cancellation-target, and exact-subject identifiers |
| Effect boundaries | Declared effect classes plus **receiver-owned** effective-action classification |
| Receiver admission | Explicit evidence bound to exact message and operation digests; fail-closed outcomes |
| Integrity and retries | Canonical bounded JSON, SHA-256 content digests, semantic freezing, operation-level replay handling |
| Review and cancellation | Receipt *claims* requiring independent confirmation; cancellation and idempotency constraints |

Intranel messages are **data, never authorization**. Transport authentication, a sender's claimed capabilities, a valid envelope, or a matching receipt does not by itself permit an effect. The receiver must establish current, independent evidence for the exact target, operation, effective action, authority, and constraints. See the normative [protocol specification](spec/INTRANEL_1.md).

## Python reference implementation

The repository contains a Python package (`src/intranel`) requiring Python **3.12+**. Install the package from a permitted checkout for local evaluation:

```bash
python -m pip install -e .
```

A small, read-only example with **generic service identities**:

```python
from intranel import canonical_json_bytes, parse_message

message = parse_message({
    "protocol": "INTRANEL/1",
    "origin": "agent:planner",
    "actor": "agent:planner",
    "target": "service:catalog",
    "reply_to": "agent:planner",
    "message_id": "msg-001",
    "conversation_id": "workflow-001",
    "performative": "QUERY",
    "effect_class": "READ_ONLY",
    "security_profile": "OPEN",
    "subject": "catalog-status",
    "payload": {"include": ["revision"]},
})

wire_bytes = canonical_json_bytes(message)
print(wire_bytes.decode("utf-8"))
```

The example **only validates and canonically serializes a message**. It does not send, authenticate, execute, authorize, or prove delivery. Applications must supply their own transports, identity verification, access-control decisions, and effect handlers.

The Python API exports `parse_message`, `IntranelMessage`, `canonical_json_bytes`, `content_digest`, `admit`, and related admission and identity types. Consult [`src/intranel/__init__.py`](src/intranel/__init__.py), [the message parser](src/intranel/message.py), and [receiver admission](src/intranel/admission.py) for the actual interfaces.

## Integration contract

1. Construct a `INTRANEL/1` envelope with explicit, independently addressable roles and a pinned subject when required.
2. Validate and serialize the envelope using the source-defined parser and canonical encoding.
3. Transport the packet through a separately authenticated and governed channel.
4. At the recipient, derive the **effective action** from trusted receiver-owned handler metadata; do not accept the sender's `effect_class` as permission.
5. Bind evidence and authorization to the exact message/operation/target and check replay, constraints, expiry, and currentness before any effect.
6. Treat ACKs and receipts as claims until independently observed, verified, and correlated.

The reference admission routine supports fail-closed decisions such as `ALLOW`, `REJECT`, `QUARANTINE`, `CONFLICT`, and `DUPLICATE`; its output must not be mistaken for a deployed authorization provider or an independently verified external effect.

### Optional local coordination example

An **opt-in, four-role local coordination pilot** is included for examining canonical wrappers, causal SQLite observation, bounded public-comment polling, and staged receiver correlation. This is a test/pilot implementation, not a running background service, a secure transport, or an installed production integration. Observed replies are unauthenticated until separately verified; local SQLite snapshot consistency does not provide concurrent-writer currentness guarantees.

See [four-role coordination](spec/FOUR_ROLE_COORDINATION_V1.md), [causal inbox](spec/FOUR_ROLE_CAUSAL_INBOX_V1.md), and [atomic receiver](spec/FOUR_ROLE_ATOMIC_RECEIVER_V1.md). Historical project-specific pilot identities and continuation notes are retained in [the integration history](docs/continuation/INTRANEL_INTEGRATION_CONTINUATION_20261016_V1.md), not prescribed as setup requirements.

## Test and safety boundaries

From a permitted checkout:

```bash
python -m pip install -e ".[test]"
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
python scripts/check_editor_startup_source.py
```

These are repository-defined **source and test checks**. They do not establish deployment, end-to-end transport confidentiality, holder authorization, actual command execution, or live-system security. CI also checks editor-startup task surfaces in the checked-out tree before dependency installation; it cannot prove whether a different historical checkout previously executed unsafe local startup code.

Read [`spec/INTRANEL_1.md`](spec/INTRANEL_1.md) for protocol guarantees and exclusions. **Not implemented here:** production cutover, encryption/key management, binary transport, delegated authority, proof of receipt truth, or hidden reasoning transfer.

## Status and scope

This repository provides a source-visible protocol specification and testable Python reference implementation. It is suitable for protocol evaluation and interoperability design under its license; a production deployment requires independent authentication, authorization, transport and concurrency controls, and verification of the particular integration.
