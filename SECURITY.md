# Security Policy

Intranel treats syntax, transport, authentication, confidentiality, authority, and effect admissibility as separate concerns.

## Secrets

Do not commit real private keys, bearer tokens, API credentials, production certificates, recovery secrets, or other credentials to this repository. Interoperability vectors must use inert identifiers and placeholders only.

## Cryptography

V1 defines `OPEN`, `PRIVATE`, and `SEALED` semantic security profiles but does not provide a cryptographic implementation. Do not label a transport encrypted/authenticated merely because it carries an Intranel security-profile field.

Future cryptographic work must use reviewed standard primitives and explicit replay protection rather than protocol obscurity or a proprietary cipher.

## Authority

Authentication proves only what the authentication mechanism actually proves. It does not grant operational authority. Receivers must independently validate authority scope, exact subject, constraints, effect class, and replay/idempotency state.

## Reporting

Security defects should be handled in the repository's private review/issue surfaces and should avoid publishing real secrets or exploit credentials in examples.
