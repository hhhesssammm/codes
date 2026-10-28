# Every changed or added file

This patch is relative to `b9cc9aa00a6f7e4787d30f2fbcbd43af95edc9bc`. Paths below are relative to the repository root. **Apply the complete patch:** the Add/Replace column describes what `git apply` does automatically. For a manual update, add every Add file and replace every Replace file from the patched checkout; do not mix module versions.

| Path | Laptop action | What changed and why |
|---|---|---|
| `.gitattributes` | Add | Add LF text policy and binary exceptions so Windows checkouts preserve the delivered byte hashes. |
| `.gitignore` | Replace | Repair the invalid IDE glob; exclude private local configuration copies. |
| `ANNOTATION_GUIDE.md` | Replace | Clarify retained-error versus correction roles and reject contradictory transition inventories. |
| `CHECKSUMS.sha256` | Replace | Regenerate the release manifest for the complete updated source, documentation, tests and evidence. |
| `PROTOCOL.md` | Replace | Document adaptive candidate expansion, metadata boundaries, partial display, proper paired bounds and the offline proxy. |
| `README.md` | Replace | Identify version 0.1.1 review materials and link to the exact update instructions. |
| `WINDOWS_GUIDE.md` | Replace | Direct repository users to the patch guide; add deep validation and explicit returned-model matching; distinguish baseline CI. |
| `pyproject.toml` | Replace | Bump package version to 0.1.1 without changing dependencies. |
| `review/CHANGELOG_FILES.md` | Add | This exhaustive Add/Replace map for applying and reviewing the patch. |
| `review/LAPTOP_UPDATE.md` | Add | Provide exact PowerShell setup, patch application, input reuse, tests, deep validation, optional diagnostic and troubleshooting commands. |
| `review/LITERATURE_REVIEW.md` | Add | Record verified primary sources, publication status, search scope and the limits of applying long-document RAG methods to captions. |
| `review/REVIEW_REPORT.md` | Add | Present demonstrated defects, implemented fixes, actual comparison results and remaining scientific limitations. |
| `review/validation/README.md` | Add | Explain the scope and limitations of each evidence file, separating pre-fix failures from final passing tests. |
| `review/validation/baseline_github_ci.json` | Add | Preserve fetched success metadata for the original commit only, across Windows/Ubuntu and Python 3.12/3.13. |
| `review/validation/baseline_tests.xml` | Add | Save the actual original-code 46-test passing run. |
| `review/validation/deep_validation.json` | Add | Save the completed full-source caption/parent, identity, FTS and crop-receipt checks. |
| `review/validation/donor_audit_report.json` | Add | Save the actual seeded comparison, corpus profile, selected IDs, source/code hashes and limitations. |
| `review/validation/donor_rankings.jsonl` | Add | Save all per-query representation rankings and source identities underlying the diagnostic results. |
| `review/validation/environment.json` | Add | Record the actual Linux development environment; these paths are provenance, not laptop configuration values. |
| `review/validation/reproduced_regressions.xml` | Add | Save the actual seven deliberately failing pre-fix regressions as defect evidence. |
| `review/validation/updated_tests.xml` | Add | Save the actual clean-environment updated suite: 71 passed, no failures. |
| `src/brain_imager_phase3/__init__.py` | Replace | Keep the exported package version synchronized at 0.1.1. |
| `src/brain_imager_phase3/annotations.py` | Replace | Bind crop receipts to official identities and prior hashes; enforce focal eligibility and consistent claim transitions. |
| `src/brain_imager_phase3/cli.py` | Replace | Expose validate --deep and the bounded CPU-only retrieval-audit command. |
| `src/brain_imager_phase3/evaluation.py` | Replace | Reject duplicate/relabelled outputs; add adjudicable denominators, proper paired bounds and missing planned contrasts. |
| `src/brain_imager_phase3/planning.py` | Replace | Hash the annotation UI; log search windows, invisible retrieved captions and partially displayed captions. |
| `src/brain_imager_phase3/provider.py` | Replace | Reject responses from an unexpected model instead of accepting them into a pinned run. |
| `src/brain_imager_phase3/retrieval.py` | Replace | Expand duplicate-heavy candidate windows; add audit-only chunk metadata; validate complete identities and source text/parent mappings plus external FTS content. |
| `src/brain_imager_phase3/retrieval_audit.py` | Add | Implement reproducible donor-only comparisons of intact captions, unindexed metadata, short fragments and same-image bundles; export rankings and provenance. |
| `tests/test_audit_regressions.py` | Add | Reproduce crop-identity, donor-window and annotation-consistency failures and verify the fixes using synthetic fixtures. |
| `tests/test_evaluation.py` | Replace | Test identification bounds and rejection of duplicate paired-analysis units. |
| `tests/test_pipeline.py` | Replace | Test that outputs cannot duplicate jobs or relabel planned condition/decoder identities. |
| `tests/test_provider_and_budget.py` | Replace | Test rejection of a mismatched returned model without a live API call. |
| `tests/test_release.py` | Add | Test checksum verification for changed/missing files and unsafe paths. |
| `tests/test_retrieval.py` | Replace | Check metadata stays out of prompts, source IDs remain traceable and partial display is explicit. |
| `tests/test_retrieval_audit.py` | Add | Test withheld annotation/duplicate exclusion, chunk parent/span provenance, metadata ranking neutrality and deep source mismatch detection. |
| `verify_release.py` | Add | Add a dependency-free SHA-256 release verifier with path traversal and duplicate-path guards. |

Total: **37 files** (19 added, 18 replaced). No files are deleted.

Unchanged assets include the approved Phase 2 ZIP, tokenizer cache, all three dependency requirement files, default configuration, seven condition definitions and provider request template. Existing source/checkpoint provenance is preserved. No images, decoder outputs, human judgments or generated experimental results are invented or replaced.

Old plans and outputs are preserved in their original workspace. Their frozen code digest intentionally differs after the update; they must not be resumed or pooled silently with a new run. The new guide uses a separate workspace and reuses only verified source inputs.

The root `validation/` files and `INSPECTION_AND_VALIDATION.md` remain the historical delivery record. New evidence is under `review/validation/`. No remote commit or pull request was created; the supplied patch is the update.
