# Intranel Chat Communication Bus Profile V1

This profile describes durable carriage of `INTRANEL/1` messages through `thebrazenbeard/chat-communication-bus`. It is a transport profile, not an authority source.

## Placement

Intranel traffic carried through the Bus remains append-only. A compatible message may be stored under the existing `messages/` surface using the Bus's current routing conventions. This profile does not authorize changing Bus topology, branch protections, credentials, or canonical routing.

## Durable wrapper

A Bus wrapper should expose enough metadata to locate and verify the semantic message without duplicating governance semantics in prose. These are **logical semantic slots**, not necessarily literal Bus header names:

- `intranel_protocol: INTRANEL/1`
- Intranel semantic `message_id: <message_id>` (distinct from the Bus writer-local `message_id`)
- Intranel semantic `operation_id: <operation_id-or-null>`
- `semantic_sha256: <64-hex canonical message digest>`
- Intranel semantic `origin: <origin address>`
- Intranel semantic `target: <target address>`

The canonical Intranel semantic message remains the payload of record. If wrapper metadata and the canonical payload disagree, the result is `CONFLICT`.

### Proposed Bus-document wire mapping (source stage; optional)

`ccb-core` has a proposed read-only document codec for this profile. It is a
candidate **wire encoding** of the slots above, not a new Intranel protocol
version, an installed integration, or a replacement for current Bus writer-lane
and routing controls. The existing Bus `message_id` header belongs to the
**physical writer lane**. It must not be overwritten by Intranel's semantic
packet `message_id`.

| Bus document header | Value / source |
| --- | --- |
| `message_id` | Bus writer-local delivery ID; distinct from semantic `message_id` |
| `prev_message_id` | **Optional outer Bus predecessor** from the trusted writer-lane history tip; unrelated to Intranel semantic `parent_message_id` |
| `writer` | Bus writer label; subject to external writer-lane binding |
| `intended_recipient` | Bus route; subject to external destination binding |
| `created_at` | Exact semantic `observed_at` timestamp |
| `requires_ack` | Lowercase Bus boolean from semantic `ack_required` |
| `intranel_protocol` | `INTRANEL/1` |
| `intranel_message_id_b64u` | UTF-8 bytes of semantic `message_id`, encoded as unpadded Base64URL |
| `intranel_operation_id_b64u` | Same encoding of semantic `operation_id`; **omit** this header when the operation ID is null |
| `intranel_origin` | Semantic `origin` claim |
| `intranel_actor` | Semantic `actor` claim, including any explicitly represented relay |
| `intranel_target` | Semantic `target` claim |
| `semantic_sha256` | Lowercase SHA-256 hex of the **exact canonical semantic JSON bytes** |

The Bus document body is exactly those canonical Intranel JSON bytes, without
an additional JSON wrapper, Markdown fence, or text prefix. The receiver must
compare decoded header values against the body and distinguish a wire/semantic
metadata conflict from verified execution. Encoding IDs in header-safe Base64URL
preserves valid semantic IDs that cannot safely appear in raw Bus scalar headers.
The physical Bus ID and Intranel packet ID are separate identity domains;
retry and idempotency semantics continue to use Intranel's semantic identifiers.

On an empty writer lane, the outer `prev_message_id` header is absent. After
the first append, the Bus writer supplies the current trusted lane tip as
`prev_message_id` for the next append and the receiver compares it against its
independently obtained expected predecessor. A stale or mismatched predecessor
must be held. This is Bus append-order lineage: it does **not** set, replace,
or infer Intranel's semantic `parent_message_id`, `operation_id`, or authority.

The current source-stage codec is deliberately narrower than `INTRANEL/1`:
it carries `OPEN` / `READ_ONLY` messages, including read-only `REQUEST`, but
does not carry `EXECUTE`, `CANCEL`, private messages, or mutation effects.

This mapping is intentionally **not yet a production interoperability claim**.
Trusted infrastructure must independently establish the writer lane, destination
and target mapping, and then perform full Intranel schema parsing, authentication,
authorization, replay/idempotency, and effect admission. The mere presence of
matching metadata, a digest, or a `RECEIPT` performative is not evidence of
delivery, admission, or completed effects.

## Relay semantics

Bus carriage may change `actor` only when the relay is represented explicitly in the semantic message. It must preserve `origin`. Mirroring a message does not create a new operation unless the sender explicitly assigns a new `operation_id`.

## Authority boundary

The Bus is a durable carrier. Receipt from `chat-communication-bus`, presence under `messages/`, a valid `semantic_sha256`, or a message authored on a known branch **does not grant authority**. The receiver still performs Intranel admission checks.

## Replies

`reply_to` controls the semantic response route. Bus conventions such as thread termination may be represented in payload/status conventions, but cannot override the Intranel performative or prohibited effects.

## V1 limitation

This document defines carriage semantics only. No automatic Bus parser/writer, encryption layer, or production routing mutation is implemented by Intranel V1.
