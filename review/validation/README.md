# Evidence produced during the repository review

These are actual saved outputs from 28 October 2026. They are not results of
the proposed brain-caption generation study. No API calls were made.

| File | What it establishes | What it does not establish |
|---|---|---|
| `baseline_tests.xml` | Original cloned implementation: 46 tests passed. | Adequacy of the original tests or absence of the subsequently reproduced defects. |
| `reproduced_regressions.xml` | Seven added synthetic regressions failed before fixes: crop association, donor-window truncation, contradictory transitions, output identity/duplication and model mismatch. | Corruption of any real input or an unsuccessful final test run. These failures were intentional defect evidence. |
| `updated_tests.xml` | 71 tests passed in a newly installed Python 3.12 environment on Linux. | Native Windows execution of this patch, live provider compatibility, or scientific factuality. |
| `baseline_github_ci.json` | Retrieved job metadata for the original commit's successful Windows/Ubuntu Python 3.12/3.13 CI jobs, with direct URLs. | CI execution of these unpushed modifications. |
| `environment.json` | Actual development interpreter, SQLite and package versions and paths; no API key was present. | Paths that should be copied into a laptop configuration. Use `LAPTOP_UPDATE.md` instead. |
| `deep_validation.json` | Exact approved identity sets; all 611,349 caption text/parent associations; FTS consistency; 2,946 cached rows and 20 official crop receipts. | Fresh image-based visual review or a new global near-duplicate screen. |
| `donor_audit_report.json` | One seeded, CPU-only donor-caption comparison; selected IDs, source/code hashes, token-length profile, metrics and runtime. | The central error-persistence hypothesis, statistically established superiority or a token-matched generation comparison. |
| `donor_rankings.jsonl` | All 400 query/representation rankings underlying the diagnostic aggregates, with source-caption IDs, parent IDs and text hashes. | Human relevance or visual-truth judgments. |

The donor audit also generated `queries.jsonl` locally. It is not bundled here:
the report's caption IDs, seed, approved source ZIP and supplied command recover
the exact queries without redistributing an additional caption-text export.
The diagnostic removes each held-out query annotation and all exact normalized
full-caption duplicates before building any representation. Same-image donor
captions are deliberate positives in this **proxy task**; NSD target images
remain excluded from all candidate donors.

Developer paths and hostnames in logs identify the actual environment and are
retained as evidence. Synthetic test labels are not research annotations.
The older root `validation/` folder and `INSPECTION_AND_VALIDATION.md` are the
historical package-delivery record; this directory documents the later review.
