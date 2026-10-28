# Brain-Imager RAG repository review — 28 October 2026

**Recommendation:** retain whole COCO captions as the production retrieval unit,
apply the validation fixes, and review the resulting code before model experiments.
Metadata should establish identity, exclusion and traceability. It is not a new
source of target-image facts. Image-level aggregation is a promising separate
retrieval hypothesis, not an established improvement in brain-caption factuality.

## Scope and inspected source

- Repository: https://github.com/hhhesssammm/codes
- Audited commit: `b9cc9aa00a6f7e4787d30f2fbcbd43af95edc9bc`, branch `master`.
- GitHub reported read permission and no push permission. Changes are supplied
  as a patch; no remote branch, pull request or merge is claimed.
- The cloned files matched the earlier Phase 3 package except for `.gitignore`.
  No `AGENTS.md` was present. Source modules, configuration, dependencies,
  PowerShell scripts, tests, protocol and the nested Phase 2 audit were inspected.
- The exact bundled Phase 2 archive SHA-256 remains
  `f03a3b653c94dbda169996f48f5dfd001e24c1398457e3eed4943a817df12c25`.
  Its 45 members and pinned manifests passed validation. It was not modified.

## Findings and implemented fixes

The original suite passed 46 tests. Seven new regression cases then failed on
the original implementation, reproducing the first five findings below. These
are demonstrated validation gaps, not claims that the real data were corrupted.

| Priority | Finding | Consequence | Implemented change |
|---|---|---|---|
| High | Crop receipts checked bytes but not their official stimulus association. | Two correctly hashed crop files could be attached to the wrong images. | Verify filename, official URL, NSD ID and COCO join against pinned Phase 2 metadata; enforce prior crop hashes where available. |
| High | A review could mark an error omitted/corrected while its inventory still asserted the false proposition. | Apparent improvement could be a bookkeeping contradiction. | Reverse consistency checks require persistence when that assertion remains; omission cannot coexist with an explicitly supported correction. |
| High | Output coverage used a set without rejecting duplicate jobs or comparing all identity fields with the plan. | Duplicate or relabelled output records could enter review. | Require unique jobs and exact condition, repeat, subject, decoder variant, stimulus, request, context and caption provenance. |
| Medium | Deduplication stopped at a fixed candidate window. | Many identical captions could hide valid lower-ranked distinct donors. | Expand the window deterministically until top-k distinct donors or exhaustion; retain ordering and leakage checks. |
| Medium | Returned API model ID was logged but not enforced. | An unexpected model response could enter a nominally pinned run. | Reject a response whose model differs from the configured snapshot; retain normal failure/cost accounting. |
| Medium | Existing-index validation primarily relied on its seal and counts. | A resealed bad caption-to-parent assignment required a stronger check. | Compare full ID sets on normal validation; `validate --deep` checks every caption text/parent against the pinned COCO ZIP and checks external-content FTS consistency on an in-memory copy. |
| Medium | Differences between lower or upper persistence endpoints were easy to mistake for bounds on the treatment difference. | Both conditions being unresolved could misleadingly appear to imply a zero-width difference. | Export proper paired bounds `[L_B-U_A, U_B-L_A]`, separately from sampling intervals and adjudicable point estimates. |
| Low | Partial caption display was logged indirectly through full context. | Relational information cut by token matching was hard to count. | Add partial-caption and invisible-caption counts plus explicit displayed-unit flags. The matching policy itself is preserved. |
| Low | `.idea\` was an invalid ignore glob; source hashes were vulnerable to Windows newline conversion. | Search warnings and avoidable checksum mismatches. | Correct the glob; add LF Git attributes and a standard-library release verifier. |

Also enforced consistency of frozen diagnostic eligibility, included annotation
UI bytes in the code digest, and added the decoded-to-rewrite and remaining
factorial contrast. All seven conditions and their source/context assignments
are preserved. No semantic tags, target annotations, reference captions, NSD
IDs or decoder metadata are added to the generator prompt.

## Actual data-level checks

Using the previously verified local inputs, the updated checks passed for:

- 982 unique sample identities and all 2,946 cached decoder-caption rows;
- all 611,349 eligible caption IDs and 122,204 parent image IDs;
- every indexed caption's exact text and parent against the pinned annotation
  ZIP, including FTS external-content consistency;
- all 1,083 exclusions, including the 83 conservative potential-near-duplicate
  exclusions from Phase 2;
- 20 pilot crop receipts, their bytes and official identity mappings.

The original SQLite database hash stayed
`42a4cdd11c551649e9c2bbaee2cd466957f892d1515150ab4aa3ab990182a60f`.
No image, decoder, trial-level alignment or full near-duplicate screen was
recomputed. Checking receipts is not new visual review of the crops.

## Controlled CPU-only retrieval diagnostic

Full-corpus token profiling with `o200k_base` found a mean of **11.80 tokens**,
median **11**, 95th percentile **16**, 99th percentile **21**, and maximum **65**.
Thus ordinary long-document chunk sizes would not split these captions at all.

The diagnostic used seed `20261028`, 10,000 eligible donor images, and 100
held-out donor captions. It started with 50,026 captions; withholding query
records and their exact normalized duplicates left 49,925. No query lost its
remaining positive image and no excluded NSD image entered this diagnostic.
Each query's remaining same-image captions define the positive parent image.
This is intentionally a different task from the production target-excluded RAG
experiment, and uses no decoded-caption truth labels or generation calls.

| Representation | Indexed units | Hits@1 | Hits@3 | Hits@10 | MRR@10 | Mean raw top-3 context tokens |
|---|---:|---:|---:|---:|---:|---:|
| Whole caption | 49,925 | 24% | 36% | 50% | 0.3198 | 45.88 |
| Whole caption + unindexed metadata | 49,925 | 24% | 36% | 50% | 0.3198 | 45.88 |
| Eight-word fragments | 92,470 | 17% | 28% | 37% | 0.2329 | 34.30 |
| Same-image caption bundle | 10,000 | 38% | 53% | 62% | 0.4637 | 179.48 |

Metadata-only rankings and numerical scores matched exactly for all 100 queries.
This confirms the intended invariant; it is not an accuracy gain. Short fragments
performed worse in this one diagnostic. Bundles retrieved the positive parent
more often, but provided 3.91 times as much text and changed BM25 document-length
statistics. Their higher score does not establish a fair generation advantage.
Nor do these point estimates establish statistical significance or universal
superiority: only one seed, a sampled corpus and a caption-to-caption proxy were
tested. Relevant alternative donor images are not labelled as positives here.

The final diagnostic completed locally without an API. Per-query measured means
were about 30 ms for captions, 43 ms for fragments and 13 ms for bundles; these
depend on different index sizes, the Linux host and cache state. They are not
Windows performance promises. Corpus profiling, audit outputs, rankings, source
hashes and selected IDs are available in `review/validation/` and reproducible
with the supplied command. Temporary audit indexes never replace `corpus.sqlite3`.

## Technical and scientific decisions

1. **Keep one intact caption per indexed production unit.** It is already short
   and naturally bounded. Extra splitting can break attributes and relations.
2. **Enrich audit metadata only.** Store chunk ID, parent image, source-caption
   IDs and text hash. Use approved IDs for filtering and deduplication. Do not
   embed opaque IDs, filenames or human error labels into searchable text.
3. **Do not prepend LLM-generated explanations.** A caption has no long source
   document supplying omitted context. Such explanations add cost and another
   hallucination mechanism; unrelated adjacent images are not valid context.
4. **Keep image bundles in the offline diagnostic.** A future approved ablation
   could rank parents but emit a fixed number/budget of intact donor captions,
   followed by blinded relevance/factuality evaluation. That is not activated
   in the production runner by this patch.
5. **Keep crop-grounded human evaluation.** Caption-reference similarity and
   object-only metrics do not cover the required action, count and relation
   transitions. Missing references are not proof that a claim is false.

Evidence and publication status for these choices are documented in
`LITERATURE_REVIEW.md`. Query rewriting and RAG vulnerability to misleading
context are established topics. The defensible question remains the narrow
paired intervention in verified brain-decoded captions; metadata itself is not
a novelty claim.

## Validation status and remaining limits

- **71 automated tests pass** in the updated implementation; the original
  baseline passed 46. The seven deliberately failing pre-fix regressions are
  retained as evidence, separate from the successful final suite.
- Python compilation, deep real-data checks and the offline donor comparison
  completed. No paid model endpoint, decoder or training job was executed.
- Dependencies are unchanged. A fresh Python 3.12 virtual environment installed
  the pinned requirements and editable package, passed `pip check`, and passed
  all 71 tests. Version is now `0.1.1`; CPU retrieval remains sufficient.
- The **original commit** has a successful [GitHub Actions run](https://github.com/hhhesssammm/codes/actions/runs/40652671109)
  on Windows and Ubuntu, each with Python 3.12 and 3.13. The fetched job metadata
  is included in `validation/baseline_github_ci.json`. That is baseline evidence,
  not Windows validation of this patch. The updated code was tested locally on
  Linux; native Windows/PowerShell execution of the patch is still unverified.
- Prefix token clipping can still truncate a relation; it is now explicit in
  diagnostics. Random controls are conditional on length. One subject, small
  error counts, oracle repairs, annotator expectations, pretraining overlap and
  unknown near-duplicates still limit interpretation.
- Exact checkpoint hashes and historical Brain-Imager pre/post pairs remain
  unavailable. The approved named public caches remain the implemented route.
- Real human baseline labels, verified focal repairs and post-generation
  judgments remain required. No central research hypothesis has been tested
  here. Stop at review of these changes before the next research phase.
