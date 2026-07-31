---
name: verify-everweb-change
description: Verifies EverWeb code changes against architecture invariants, contracts, tests, security boundaries, and Definition of Done. Use after substantive edits, before completion, or when reviewing a diff.
paths:
  - "src/everweb/**/*.py"
  - "tests/**/*.py"
  - "config/**/*.toml"
---

# Verify EverWeb Change

Perform a defect-first verification. Do not edit while acting as an independent verifier.

## Checks

1. Inspect the complete diff and list affected packages and behaviors.
2. Map each behavior change to the canonical design section and relevant `INV-*`.
3. Check dependency direction:
   - no infrastructure imports in domain;
   - no provider SDK in core;
   - no adapter-to-adapter dependency;
   - no production import from harness.
4. Check runtime correctness:
   - Policy and StepMeter remain authoritative;
   - side effects have receipts;
   - ambiguous writes reconcile rather than retry;
   - failure paths still persist and emit.
5. Check evidence and output:
   - claims remain evidence-bound;
   - complete sets require StopProof;
   - output is a chronological trace projection;
   - serialization remains pure.
6. Check security:
   - no direct target HTTP;
   - untrusted data cannot control execution;
   - no secret or raw reasoning persistence.
7. Check tests at the appropriate unit, contract, scenario, or fault level.
8. Run available targeted checks. Separate deterministic replay conclusions from statistical live conclusions.

## Output

Report actionable findings first, ordered P0 to P2, with file locations and violated contract. Then list checks run and residual risks. If there are no findings, say so explicitly without claiming unrun checks passed.
