# Intranel Chat Communication Bus Profile V1

This is a **historical private-era transport profile** for `INTRANEL/1`. `thebrazenbeard/chat-communication-bus` became PUBLIC on 2026-10-29; this profile is not a current destination or a deployable integration contract.

## Public-transition hold

**Do not write confidential Intranel messages** to `thebrazenbeard/chat-communication-bus` branches, issues, PRs, comments, workflow logs, or `messages/` paths. The repository and reachable historical Git objects are public. Neither a branch name nor a valid payload digest establishes confidentiality, writer identity, or authorized delivery.

Reusable CCB/Radar *source code* belongs in `thebrazenbeard/ccb-core`; that public code repository is not a private mailbox, provider deployment, or authority source either.

A future private carrier requires Patrick's exact authorization for the target, a separately access-controlled and authenticated host, verified current writer/reader roles, and durable transport/readback evidence before admission. Until such a carrier is qualified, treat this profile as **HOLD_HISTORICAL_ONLY**. A public-safe document or sanitized demonstration may reference a source PR but must not carry private task content or reveal private topology.

## Historical placement semantics

Within an independently authorized private carrier, append-only envelopes and a `messages/`-like path may be useful. The old GitHub `messages/` branch layout is historical evidence, not permission to use that layout now. This profile does not authorize changing Bus topology, branch protections, credentials, or canonical routing.

## Durable wrapper

A Bus wrapper should expose enough metadata to locate and verify the semantic message without duplicating governance semantics in prose:

- `intranel_protocol: INTRANEL/1`
- `message_id: <message_id>`
- `operation_id: <operation_id-or-null>`
- `semantic_sha256: <64-hex canonical message digest>`
- `origin: <origin address>`
- `target: <target address>`

The canonical Intranel semantic message remains the payload of record. If wrapper metadata and the canonical payload disagree, the result is `CONFLICT`.

## Relay semantics

Bus carriage may change `actor` only when the relay is represented explicitly in the semantic message. It must preserve `origin`. Mirroring a message does not create a new operation unless the sender explicitly assigns a new `operation_id`.

## Authority boundary

A separately authenticated, qualified Bus carrier may be durable; public GitHub alone is not that carrier. Receipt from `chat-communication-bus`, presence under `messages/`, a valid `semantic_sha256`, or a message authored on a known branch **does not grant authority**. The receiver still performs Intranel admission checks.

## Replies

`reply_to` controls the semantic response route. Bus conventions such as thread termination may be represented in payload/status conventions, but cannot override the Intranel performative or prohibited effects.

## V1 limitation

This document records historical carriage semantics only, and its provider route is held after the public transition. No automatic Bus parser/writer, encryption layer, or production routing mutation is implemented by Intranel V1.
