# Intranel V1 Interoperability Vectors

These vectors freeze canonical `INTRANEL/1` message examples. Digests are SHA-256 of canonical UTF-8 JSON generated from the parsed semantic message, not signatures and not authority proofs.

- `query-open.json` `sha256:888981596be808a210652fb9c576aefc60a461a763bc21cb4a1420138d4bc137`
- `relay-review.json` `sha256:8590f5d830451bc53488c0d6f6ffe03949566eb5806ecdccbfe16e0dd06c09a6`
- `execute-private.json` `sha256:eea78768a0eeb04ca7db4e87ec2e4614433eceaaf62342dc92eebd28ba39fae3`

A conforming implementation must parse each vector, preserve its semantics, and reproduce the listed digest. The canonical projection includes every defined nullable field, including `target_operation_id: null` when no cancellation target exists.
