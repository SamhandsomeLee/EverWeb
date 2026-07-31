---
name: failure-to-regression
description: Converts a real EverWeb run failure into a minimal deterministic regression fixture. Use when diagnosing live failures, replay divergence, incorrect gates, bad terminal output, or provider and browser recovery defects.
paths:
  - "var/runs/**"
  - "tests/fixtures/**"
  - "tests/scenario/**/*.py"
  - "tests/fault/**/*.py"
  - "src/everweb/harness/**/*.py"
---

# Failure to Regression

## Workflow

1. Preserve the original run manifest, trace, evidence, receipts, diagnostics, and relevant artifacts.
2. Validate checksums and identify the first divergent event, not merely the final symptom.
3. Classify the divergence as contract, perception, action, effect verification, evidence, gate, route, persistence, serialization, or adapter failure.
4. Remove unrelated events while preserving the smallest state and receipt sequence that reproduces the defect.
5. Redact secrets and unstable external identifiers.
6. Create a deterministic fixture containing:
   - task and capabilities;
   - minimal observations and model receipts;
   - required artifacts;
   - optional fault schedule;
   - contract-focused expected assertions.
7. Add one bug-specific assertion at the first divergence. Avoid full-output snapshots unless the output contract itself failed.
8. Confirm the fixture fails before the fix and passes after it.
9. Run adjacent regression cases to detect overfitting.

Do not modify sealed fixtures or feed sealed per-task outcomes back into implementation, prompts, or knowledge.
