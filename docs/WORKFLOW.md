# 🔄 Development, Review & Deployment Workflow

## Overview
This document outlines the strict iterative development protocol required for executing feature enhancements in **HOP — Enterprise AI Platform Core**.

---

## Iterative Development Protocol

For each phase / step:

1. **Design & Code Phase**:
   - Implement core code in `src/` respecting Hexagonal Architecture.
   - Implement unit tests in `tests/unit/` or integration tests in `tests/integration/`.

2. **Review & Audit Phase**:
   - Create a review file `docs/reviews/review_step_X.md`.
   - Audit code for type safety, edge cases, exception handling, and performance.
   - Run full test suite: `pytest`.

3. **Debugging & Refinement Loop**:
   - If any test fails or linting/typing error exists, fix the issue immediately.
   - Re-run `pytest` until 100% of tests pass cleanly with zero warnings/errors.
   - Update `docs/reviews/review_step_X.md` declaring verification completed.

4. **Git Commit Phase**:
   - Update `docs/DEVELOPMENT_MEMORY.md` with phase completion details and status.
   - Execute a git commit with a descriptive commit message following conventional commits format.

---

## Guidelines for Review Files (`review_step_X.md`)
Each review document MUST contain:
- Step Title & Scope
- Files Added / Modified
- Test Execution Log
- Self-Audit checklist (Hexagonal rules, type hints, edge cases, error handling)
- Verification Result (`PASSED`)
