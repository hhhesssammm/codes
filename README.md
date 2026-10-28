# Brain-Imager Phase 3 — runnable pilot

A Windows-compatible Python package for testing whether caption-query retrieval
reinforces a pre-existing, visually verified error in a frozen fMRI-decoded
caption, and whether repairing only the retrieval query changes that persistence.

**Start with [WINDOWS_GUIDE.md](WINDOWS_GUIDE.md).** It contains exact PowerShell
commands, setup, annotation, cost controls, pilot execution and troubleshooting.
For the reviewed **0.1.1** update, use [review/LAPTOP_UPDATE.md](review/LAPTOP_UPDATE.md)
first. [review/REVIEW_REPORT.md](review/REVIEW_REPORT.md) records the bugs,
actual validation and offline chunk-representation comparison; every changed
file is listed in [review/CHANGELOG_FILES.md](review/CHANGELOG_FILES.md).
See [PROTOCOL.md](PROTOCOL.md) for the scientific estimands and limitations,
[ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md) for human review, and
[INSPECTION_AND_VALIDATION.md](INSPECTION_AND_VALIDATION.md) for actual validation.

This is Phase 3 code and an exploratory pilot workflow. No real model outputs,
factuality annotations, experimental results or paper conclusions are supplied.
Synthetic fixtures are isolated in `tests/` and labelled as such. No brain decoder,
training job, GPU library, or fMRI volume download is required.

| Condition | Caption given to generator | Context |
|---|---|---|
| `decoded` | Unchanged cached output; no generator call | None |
| `rewrite_only` | Original | None |
| `rag_original` | Original | Retrieved with original query |
| `rag_query_repaired` | **Original** | Retrieved with minimally repaired query |
| `rag_caption_repaired` | Repaired | Retrieved with original query |
| `rag_both_repaired` | Repaired | Retrieved with repaired query |
| `random_context` | Original | Token-length-matched random other-image captions |

The three repaired conditions run only where a human has preselected a
contradicted claim and verified its minimal repair. This is an oracle diagnostic;
the corrected query is not an automatically available production input.

The default is a deterministic 20-stimulus pilot using original UMBRAE subject-1
captions, one generation repeat, top-3 BM25 retrieval and a 240-token context
budget. BrainCap and MindEye2 remain separately identified options. All 1,083
Phase 2 excluded images stay outside the corpus. There is no automatic selection
of an error-enriched subset and no confirmatory experiment command.

**Inputs included:** the exact approved Phase 2 ZIP, its 2,946-row alignment
manifest, 982-row sample manifest, exclusion identities and checksums; source
code; configuration; pinned dependencies; tests; a cached public tokenizer table.
**Inputs fetched on your laptop:** hash-verified public caption files, the official
COCO annotation ZIP, and only the pilot's official NSD displayed-image PNGs.
**Inputs you must provide:** human claim labels and minimal repairs, followed by
human output review; an API key/account if you choose paid generation.

The default generator is the pinned `gpt-5.4-mini-2026-03-17` API model. Retrieval,
validation, annotation and analysis run locally on CPU. No target images, COCO
target references, error labels or neural arrays are sent to the generator.
Only the selected source caption and eligible other-image example text are sent.
Model access is account-dependent; a model error stops the run rather than
silently switching models. Prices and limitations are documented in the guide.

Outputs go under `workspace/pilot/`. The code freezes configuration, annotation,
corpus and prompt hashes; saves full request/response records without API keys;
resumes completed requests; records failed/uncertain attempts; and reports
stimulus-clustered exploratory contrasts with explicit denominators.

The project uses public cached decoder outputs, not an independently reproduced
Brain-Imager checkpoint. Original checkpoint hashes and historical Brain-Imager
pre/post-rewrite pairs remain unavailable. Passing the tests does not establish
the research hypothesis or validate human labels.

`retrieval-audit` is a separate CPU-only donor-caption diagnostic. It compares
whole captions, unindexed metadata, short word chunks and same-image bundles
without changing the production retriever or the seven experimental conditions.
Its same-image retrieval scores are not factuality results for decoded captions.
