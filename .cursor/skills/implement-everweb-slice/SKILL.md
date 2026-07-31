---
name: implement-everweb-slice
description: Implements an EverWeb feature or vertical slice without architecture drift. Use for coding tasks that add or change runtime, supervisor, browser, model, evidence, answer, output, or harness behavior.
paths:
  - "src/everweb/**/*.py"
  - "tests/**/*.py"
  - "config/**/*.toml"
---

# Implement EverWeb Slice

## Workflow

1. Read the relevant sections of `docs/architecture/EverWeb_Architecture_v2.2_Kimi_First.md`.
2. Identify:
   - affected `INV-*` invariants;
   - owning packages and allowed dependency direction;
   - current implementation week and Definition of Done;
   - unresolved `PendingTemplate` fields.
3. Inspect existing source, tests, configuration, and public interfaces.
4. Define the narrow vertical slice:
   - input;
   - public boundary;
   - persisted receipts/events;
   - expected terminal behavior;
   - explicit non-goals.
5. Add or update a failing test at the lowest sufficient level: unit, contract, scenario, fault, then live.
6. Implement the smallest change that satisfies the contract. Do not add speculative abstractions or adjacent features.
7. Preserve append-only facts, port boundaries, serializer purity, evidence binding, and emergency output.
8. Run targeted tests first, then available architecture, lint, type, and fast regression checks.
9. Review the diff for reverse dependencies, direct target HTTP, invented competition semantics, secret exposure, and weakened assertions.

## Completion report

State:

- implemented slice and non-goals;
- invariants preserved;
- tests and commands run;
- results;
- unresolved specification gaps or unverified live behavior.

Never claim success for checks that were not run.
