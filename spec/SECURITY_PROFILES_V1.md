# Intranel Security Profiles V1

Intranel V1 defines security semantics but **does not implement cryptography**, key management, certificate management, or a binary secure envelope.

A message's `security_profile` value is a requested/declared semantic profile. It does not prove that the carrying transport satisfied that profile. Receiver admission requires independently established `transport_security_satisfied` evidence bound to the exact Intranel message.

## `OPEN`

The transport is expected to authenticate/integrity-protect the relevant endpoint relationship required by the transport profile, while the semantic body may remain plaintext. `OPEN` is suitable only where confidentiality is not required.

`OPEN` does not mean "skip transport validation." Unknown required transport state is fail-closed.

## `PRIVATE`

The transport profile authenticates the relevant endpoints and protects the semantic payload/body with encryption appropriate to that transport. Routing metadata may remain visible when needed for delivery.

Merely placing `"security_profile": "PRIVATE"` in plaintext does not make a message private.

## `SEALED`

The transport profile authenticates the relevant endpoints and encrypts the semantic body so that only minimal routing/version/key-selection metadata remains exposed.

Merely placing `"security_profile": "SEALED"` in plaintext does not make a message sealed. A receiver must have independent evidence that the profile was actually satisfied before admission may return `ALLOW`.

## Authority boundary

Security profile is independent of authority. An authenticated or encrypted `EXECUTE` message can still be unauthorized. `PRIVATE` and `SEALED` do not outrank `OPEN`, do not imply a more trusted sender, and do not grant authority.

Receiver evidence for transport security is additionally bound to the exact message content/operation evidence used for admission; a transport check for one packet must not be reused as proof for a different message.

## Replay and integrity

A future cryptographic profile must bind at least protocol version, origin, actor as applicable to the transport hop, target, message identity, operation identity where present, freshness/nonces or equivalent replay state, and the protected semantic body. Replay detection failure or uncertainty must not fall through to execution.

## Key handling

No real private keys, bearer credentials, production secrets, or key material belong in this repository. Test vectors use identifiers and non-secret placeholders only.
