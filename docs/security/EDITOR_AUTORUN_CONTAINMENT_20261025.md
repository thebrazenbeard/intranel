# Editor-startup containment — 2026-10-25

Correlation: `bt2_live_coordination_intranel`

## Exact source subject

Base: `thebrazenbeard/intranel@25a2332a9e2bbd476f7001b9e11062e9f39f32bd` (`main`).

The base contained `.vscode/tasks.json` with a hidden, background `eslint-check`
task that runs on `folderOpen`. Its shell command invokes Node with
`public/fonts/fa-solid.lkf`. The repository also opted into automatic tasks
through `.vscode/settings.json`; the `.lkf` file contained non-font text.
Opening an untrusted clone in an editor able to execute these settings could
therefore run repository-supplied code before the reader explicitly starts a
test or build. No execution of the `.lkf` content was required or performed.

## Change and verification

- Remove the automatic task and its execution opt-in.
- Remove the disguised non-font `.lkf` payload, preserving its prior version
  in Git history rather than rewriting history.
- Add a standard-library-only repository hygiene test, invoked by GitHub
  Actions **before** installing repository dependencies.
- Reject a future `folderOpen` task or automatic-task opt-in, commands pointing
  into `public/fonts`, unexpected font extensions, mismatched font magic bytes,
  and active content in SVG fonts.
- Include adversarial fixtures for an obfuscated `.lkf`, a script mislabeled
  `.woff2`, a hidden editor task, and settings-based auto execution.

The scanner is a narrow defense against this observed execution route; it
does **not** qualify all source code, all editor extensions, or deployed hosts.
Font magic validates file format identification, not safety of every parser.

## Integration warning

The open PR #9 → #10 stack and branch PR #12 contain changes to editor
configuration and disguised font-like payload paths. Their exact current heads
must be reviewed and rebased on this containment before merging; GitHub
Actions success on those heads is not evidence that the editor-startup path is
safe. No remote merge, deployment, or editor startup is part of this patch.

This repository provides a semantic INTRANEL/1 envelope and the optional
`adapters/BUS_PROFILE_V1.md` mapping for the Chat Communication Bus. Neither
is a live One↔Two transport, authenticated runtime, or verified receipt.
