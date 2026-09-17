# Intranel V1 Interoperability Vectors

These vectors freeze canonical `INTRANEL/1` message examples. Digests are SHA-256 of canonical UTF-8 JSON generated from the parsed semantic message, not signatures and not authority proofs.

- `query-open.json` `sha256:03203ef8bb361e13178368e143dbad0dbe899f890356538369e3b624ec6b070a`
- `relay-review.json` `sha256:0bd61eb9fc492ebfae58c5b41fc50f74ca4c3e1ca1fe652a8af1aa34450875fd`
- `execute-private.json` `sha256:4ac53ef01747e5ed6a20f7a425e794aa3317611893d65fb9bda274ac22e3d042`

A conforming implementation must parse each vector, preserve its semantics, and reproduce the listed digest.
