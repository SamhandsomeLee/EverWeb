---
name: reconcile-competition-contract
description: Reconciles EverWeb with a newly published official competition protocol, template, status schema, step definition, or output contract. Use only when the user explicitly requests protocol migration.
disable-model-invocation: true
---

# Reconcile Competition Contract

## Required inputs

- official template and guidance;
- current `CompetitionCapabilities`;
- current output and status contract tests;
- current competition contract digest.

If official source material is missing, stop and request it. Do not infer formal rules from OpenNavEval.

## Workflow

1. Save and digest the official source material.
2. Build a reconciliation list for:
   - task input;
   - `agent_answer`;
   - official status values;
   - step semantics;
   - wall-clock limits;
   - download and parsing behavior;
   - capture and screenshot rules;
   - output directory and atomic-write requirements.
3. Classify each item as unchanged, changed, newly specified, or still pending.
4. Implement compatibility only through `CompetitionAdapter` and `competition/` public contracts.
5. Keep core, domain, answer, and report logic free of official status strings and scorer-specific behavior.
6. Add contract tests plus at least three smoke fixtures.
7. Re-run trace projection, serializer purity, emergency output, status mapping, step accounting, and scorer compatibility checks.
8. Freeze the new digest and document rollback only after validation passes.

Report unresolved fields explicitly as `PendingTemplate`.
