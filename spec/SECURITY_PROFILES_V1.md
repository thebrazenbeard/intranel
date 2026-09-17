# Intranel Security Profiles V1

Intranel V1 defines security semantics but **does not implement cryptography**, key management, certificate management, or a binary secure envelope.

## `OPEN`

The transport is expected to authenticate the relevant endpoint identities, while the semantic body may remain plaintext. `OPEN` is suitable only where confidentiality is not required.

## `PRIVATE`

The transport profile authenticates endpoints and protects the semantic payload/body with encryption appropriate to that transport. Routing metadata may remain visible when needed for delivery.

## `SEALED`

The transport profile authenticates endpoints and encrypts the semantic body so that only minimal routing/version/key-selection metadata remains exposed.

## Authority boundary

Security profile is independent of authority. An authenticated or encrypted `EXECUTE` message can still be unauthorized. `PRIVATE` and `SEALED` do not outrank `OPEN`, do not imply a more trusted sender, and do not grant authority.

## Replay and integrity

A future cryptographic profile must bind at least protocol version, origin, target, message identity, operation identity where present, freshness/nonces or equivalent replay state, and the protected semantic body. Replay detection failure or uncertainty must not fall through to execution.

## Key handling

No real private keys, bearer credentials, production secrets, or key material belong in this repository. Test vectors use identifiers and non-secret placeholders only.
