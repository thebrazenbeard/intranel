# Intranel Chat Communication Bus Profile V1

This profile describes durable carriage of `INTRANEL/1` messages through `thebrazenbeard/chat-communication-bus`. It is a transport profile, not an authority source.

## Placement

Intranel traffic carried through the Bus remains append-only. A compatible message may be stored under the existing `messages/` surface using the Bus's current routing conventions. This profile does not authorize changing Bus topology, branch protections, credentials, or canonical routing.

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

The Bus is a durable carrier. Receipt from `chat-communication-bus`, presence under `messages/`, a valid `semantic_sha256`, or a message authored on a known branch **does not grant authority**. The receiver still performs Intranel admission checks.

## Replies

`reply_to` controls the semantic response route. Bus conventions such as thread termination may be represented in payload/status conventions, but cannot override the Intranel performative or prohibited effects.

## V1 limitation

This document defines carriage semantics only. No automatic Bus parser/writer, encryption layer, or production routing mutation is implemented by Intranel V1.
