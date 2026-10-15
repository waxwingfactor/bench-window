# Independent AI review record

Date: 2026-10-15. These are separate AI-agent reviews, not human approvals,
customer references, or reviews by another GitHub account.

## Opportunity challenge

Separate discovery and adversarial-competition agents checked the candidate
against primary research and current products. The freezer move candidate was
rejected for mature alternatives and batch overlap; core-use reconciliation was
rejected for native iLab and other existing workflows. The selected product has
low-to-moderate opportunity confidence. See research.md for the bounded finding.

## Core code review

A separate adversarial agent inspected the temporal encoding, complete resource
order branching, independent checker, strict parsing, and output handling.
It reported no blocking production defect in the reviewed core. Independent
checks included 1,600 extra brute-force oracle cases and 8,000 limited-budget
runs, hostile-text/malformed-file tests, and the supported 40-task boundary.
These counts describe reviewer checks, separate from the committed suite.

The reviewer found a test-quality gap: an invalid-assignment test originally
used incomplete result objects, reaching schema rejection before timing checks.
The test was strengthened to mutate complete genuine result envelopes.

The lead also repaired report placeholder substitution before final review,
so inserted user text is not scanned as a template, and changed output rollback
to track a file only after exclusive creation succeeds. No production behavior
was changed following the final core review recommendation.

## Acceptance testing

A separate test agent authored tests independently from the solver: 700 seeded
tiny integer problems are exhaustively enumerated and compared against solve
results. Deterministic cases cover exact lags, half-open resource handovers,
multiple simultaneous resources, observed starts, not-before replanning,
impossibility and unknown status. Additional CLI/contract tests cover installation
examples, hostile output text, input rejection, stale plans and no-clobber writes.
CI reports the final checked test count and environment matrix.

## Rendered report inspection

The lead inspected the actual generated HTML in the Codex browser at desktop
1280 by 720 and mobile 390 by 844. The title and notes wrapped at the narrow width;
the page had no horizontal body overflow. Both wide tables are named focusable
regions with header cells and captions. A Tab key focused the chronological
region; Right moved its horizontal scroll position from 0 to 40 pixels.
No runtime scripts, external assets or online service are required by the sheet.

## Scope of this review

The final code approval covers the source files identified below. Published
artifacts require separate download/install verification; see verification.md
when available. No laboratory procedure or scientific outcome was validated.

```json
{
  "__init__.py": "c95555e7ed9ec56e3ddf2e5d37f483b297e75fd2757a9085a57217145fc1824a",
  "__main__.py": "935a1c1166b0c1ea35a82256345000bf2c73ded718d77773bc27a71ecce28f7d",
  "checker.py": "1189ccfbcfaa1e617d9b1bfc6ddd16a3eb60cf7a6bf52224c7b4948cd642e916",
  "cli.py": "572b39482c07ec75baab7d1cb8be79a2164fb3e8919dc9ea47df801caafd7d77",
  "model.py": "3a1ef0c26c63ba1b96901b840228d716f13794332d18143e9aae68d43900c077",
  "report.py": "0203b450356f5458ee901c7e87517ec8cd707164d45576966cd68fd6eaf18b71",
  "solver.py": "e931436bb0353215d1b927bf67050f54971d1bfa2f0545ea5619b70d930984c7"
}
```
