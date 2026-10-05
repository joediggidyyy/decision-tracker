# Calamum workflow

Calamum is the testing substrate, not just a wrapper for one runner.
The CLI and Python facade calamum.api provide project context, catalog discovery,
execution, retained runs and job/project/domain aggregates.

## Project and catalog

Native `calamum project register` creates the root `.calamum/project.json`.
Portable shared paths remain in that descriptor. Interpreter and active-project
state belong in a machine-local overlay under `.local/calamum-config`.
Use CALAMUM_CONFIG_ROOT for this project-local state.

Resolution order is explicit --project, nearest descriptor, CALAMUM_PROJECT,
then active local state. Path precedence is explicit flags, local overlay,
descriptor, defaults. Inspect `project current`, `project show`, `project list`
and `project validate` rather than assuming the active target.

The catalog uses controlled category/profile/tag/policy vocabulary from the
Calamum README. One definition tests one concern and can combine pytest
(code assertions), sandbox_test (controlled workflow) and empirical_test
(actual observations). A lane name does not itself create OS isolation.
The catalog now binds bootstrap, core behavior, integrated recovery/CLI/security and actual browser observations.

## Evidence and reports

Use `test list`, `test show ID`, dry-run, then the bounded proof command in
CONTRIBUTING. Inspect `test runs list` and `test runs show RUN_ID`.
Each native run retains report.json, report.md, manifest.json, checksums.json,
stdout/stderr and an append-only run index under .calamum/generated/runs.

Use `test reports generate --scope project --project decision-tracker` for project aggregates,
or job/domain scopes when those contexts actually apply. Inspect reports list/show.
Aggregate output is under .calamum/generated/reports/generated. Unsigned local
evidence is not an authenticated signed release.

## Optional capabilities

Monitor capability discovery and optional signing were reviewed. Hardware/packet
capture, privileged repair and signed publication are not required for this app
bootstrap and are not activated. Future empirical browser checks must retain
real observations; placeholder output cannot replace them.

The setup receipt retains README/help inspection, installed versions, wheel hashes,
native registration/readback and verification evidence under .local/setup.

For project aggregates use the registered ID decision-tracker. In the inspected
Calamum0.3.1 build, --project . resolved context but filtered aggregates by the
literal selector, producing no matched runs. The failed attempt is retained;
the stable-ID command is the verified route. No upstream source was modified.
