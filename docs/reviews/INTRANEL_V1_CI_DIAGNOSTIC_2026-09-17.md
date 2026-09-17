# Intranel V1 CI Diagnostic — 2026-09-17

Status: `HOSTED_CI_INFRASTRUCTURE_FAILURE / LOCAL_BEHAVIORAL_GREEN / NATIVE_3_12_UNRESOLVED`

Current repaired executable protocol/source candidate under rereview: `9cd1ba4d4da67c42bc9a186818c9229213b6c762`.

## Hosted Actions evidence

GitHub-hosted Actions for this private repository repeatedly created Ubuntu and Windows jobs but failed before any workflow step ran. Observed failed jobs had `runner_id = 0`, an empty runner name, and `steps = []`; usable job logs were not produced.

Examples:

- Run `35276948595` against repaired source lineage `92276664…` failed before checkout/setup/test on both Ubuntu and Windows.
- Run `35277958142` against `bf08b0bd…` repeated the same pre-runner failure on both platforms.

Because those jobs never reached checkout, Python setup, dependency installation, tests, or compile, they are not evidence that Intranel source/tests failed. They are also not hosted GREEN evidence.

## Workflow-install correction history

Commit `bf08b0bd168aff7b176aedf16d84e89078d49210` temporarily changed the workflow install command from `pip install -e ".[test]"` to `pip install -e .` based on a stale view of the dependency declaration. The hostile-repair source had in fact added the test extra `jsonschema>=4.23,<5` for real Draft 2020-12 schema-parity tests.

Commit `88f193d57b00c066f32ed23d32eeea75c5a942cf` restores the correct `pip install -e ".[test]"` command. This correction does not explain or repair the hosted failure because the failed jobs terminate before any install step is assigned to a runner.

## Cross-repository control

A separate private repository owned by the same account (`thebrazenbeard/noema`) showed the same pre-runner signature: run `34877165774`, job `104087115199`, failed with `runner_id = 0`, empty runner name, and `steps = []`.

A public repository owned by the same account (`thebrazenbeard/rezon`) successfully completed GitHub-hosted Actions runs on 2026-09-17, including run `35266927370`.

This pattern is consistent with a private-repository GitHub-hosted runner entitlement/provisioning/billing boundary rather than an Intranel workflow-command or Python-test defect. It does not establish the exact external cause because account billing/entitlement state has not been independently read back here.

## Current local behavioral verification

After the original independent hostile review, the repaired source added receiver-owned effect classification, exact-message-bound admission evidence, immutable semantic JSON state, constraint/prohibition and transport-security evidence, cancellation-target/cancellability evidence, bound non-self-verifying receipt semantics, parser/schema parity, a restricted canonical numeric domain, and resource limits.

BT2 review then found one additional idempotency defect: a retry of a verified-complete `CANCEL` operation could return `QUARANTINE` because target cancellability was rechecked before completed-operation deduplication. Regression commit `6f010e96e81cc4d27fa127980d922089db621b12` reproduced the defect; source commit `9cd1ba4d4da67c42bc9a186818c9229213b6c762` repairs the ordering while preserving message binding, authentication/replay, effect classification, transport security, exact-subject, constraint/prohibition, and authority checks ahead of duplicate recognition.

A reconstructed executable workspace from current Git branch content was run under CPython 3.13.5:

- `PYTHONPATH=src python -m unittest discover -s tests -v` -> **83 tests, 0 failures**.
- `python -m compileall -q src tests` -> exit 0.
- The exact current schema/docs/vector blobs used in that reconstruction were checked against their Git blob identities; Python/test files were reconstructed from current connector readback for behavioral verification rather than materialized as a native Git checkout.

Follow-up documentation commits only describe the already-tested source semantics and explicitly supersede the historical self-review as current qualification evidence; they do not change executable protocol behavior.

This is useful behavioral evidence, but it is **not** native CPython 3.12 qualification and it is **not** hosted-CI GREEN evidence.

## Qualification consequence

- Hosted CI remains `UNRESOLVED_INFRASTRUCTURE_FAILURE`, not GREEN.
- Native CPython 3.12 qualification remains unresolved until an executable 3.12 environment is available.
- Local CPython 3.13.5 behavior is GREEN for 83 tests plus compile verification against repaired source `9cd1ba4d…`.
- Exact repaired source `9cd1ba4d…` requires fresh independent hostile rereview; prior review dispositions do not automatically carry across the source change.
- No merge, deployment, installation, billing mutation, runner provisioning, key operation, provider change, or Bus-topology mutation is authorized or implied by this diagnostic.
