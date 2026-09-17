# Intranel V1 CI Diagnostic — 2026-09-17

Status: `HOSTED_CI_INFRASTRUCTURE_FAILURE / SOURCE_RESULT_UNRESOLVED_BY_HOSTED_RUNNER`

Repaired source candidate under qualification: `92276664ab9dbe6adbe83b3c6f1e777e945b4965`.

Current branch includes follow-up CI-only commit `bf08b0bd168aff7b176aedf16d84e89078d49210`, which replaced `pip install -e ".[test]"` with `pip install -e .` because the project does not define a `test` extra. That workflow correction did not resolve the hosted startup failure.

## Intranel exact-run evidence

Run `35276948595` for source candidate `92276664…` created Ubuntu and Windows jobs. Both failed before any workflow step ran:

- Ubuntu job `105389753214`: `runner_id = 0`, empty runner name, `steps = []`, failure about two seconds after creation.
- Windows job `105389753456`: `runner_id = 0`, empty runner name, `steps = []`, failure about two seconds after creation.

After the CI-only install correction, run `35277958142` for `bf08b0bd…` repeated the same pre-runner failure on both Ubuntu and Windows with `steps = []`.

The job-log endpoints did not provide usable logs. Because the jobs never reached setup/checkout/install/test/compile, these runs are not evidence that Intranel Python source or tests failed. They are also not hosted GREEN evidence.

## Cross-repository control

A separate private repository owned by the same account (`thebrazenbeard/noema`) shows the same signature. Noema workflow run `34877165774`, job `104087115199`, failed in roughly three seconds with `runner_id = 0`, empty runner name, and `steps = []`.

A public repository owned by the same account (`thebrazenbeard/rezon`) successfully completed GitHub-hosted Actions runs on 2026-09-17, including run `35266927370`.

This pattern is consistent with a private-repository GitHub-hosted runner entitlement/provisioning/billing boundary rather than an Intranel workflow-command or Python-test defect. It does not establish the exact external cause because account billing/entitlement state has not been independently read back here.

## Qualification consequence

- Hosted CI remains `UNRESOLVED_INFRASTRUCTURE_FAILURE`, not GREEN.
- Do not label the Intranel source candidate as source-test FAIL from these pre-runner failures.
- Local verification and exact source/tree readback remain separate evidence.
- Independent hostile rereview may proceed against exact source candidate `92276664…` while hosted CI is unresolved.
- The later CI-only commit does not change the repaired protocol semantics under review.
- No merge, deployment, installation, billing mutation, runner provisioning, rerun that may incur spend, or other protected effect is authorized by this diagnostic.
