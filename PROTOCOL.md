# Phase 3 pilot protocol and implementation decisions

## Question and scope

On a fixed fMRI-decoded caption with a visually verified pre-existing factual
error, does querying an external caption corpus with that erroneous caption
increase error persistence compared with the same rewriter without retrieval?
Holding the original caption sent to the rewriter fixed, does a human-verified
minimal repair of only the retrieval query change persistence?

This tests an intervention in a text-processing pipeline. It is not a causal
experiment on the participant's brain and does not show that newly correct
details were neurally decoded. The code implements a short, exploratory Phase 3
pilot; later confirmatory study design and paper conclusions are out of scope.

The input is the approved BrainHub subject-1 cache, defaulting to original
UMBRAE. It is not an independently reproduced Brain-Imager checkpoint. All
variants and original sample/NSD/COCO identities remain in local output records.

## Predeclared hypotheses and comparisons

- H1: `rag_original` has higher persistence of pre-existing false claims than
  `rewrite_only`. The most focused endpoint is persistence of the preselected
  focal error. All annotated false claims are also reported.
- H2: `rag_query_repaired` has lower focal-error persistence than `rag_original`,
  with the generator source caption unchanged. This comparison is restricted
  to captions with a verified focal error and minimal repair.
- Utility constraint: an apparent reduction in errors must be considered
  alongside explicit correction, false-claim omission, retention of correct
  claims, new false/unverifiable claims and output length.

The two additional oracle cells, `rag_caption_repaired` and `rag_both_repaired`,
separate changing the source caption from changing retrieved context. They are
diagnostic controls, not fair production competitors. `decoded` establishes
the unchanged input. `random_context` controls for extra example text using
random eligible donors conditional on sufficient length, clipped to match the
original displayed context under the declared tokenizer.

All pairwise contrasts are reported as **second condition minus first**. For
example, `rag_query_repaired minus rag_original` should be negative under H2.
The program does not decide whether a hypothesis is confirmed.

## Sampling and human repairs

The default 20 stimuli are chosen by deterministic hash ordering of complete
Phase 2 similarity groups, without consulting errors or generated outputs.
The one two-image similarity group cannot cross pilot/reserved boundaries.
The full 982-target exclusion set remains outside retrieval regardless of which
images enter the pilot. This is a group-based, reproducible pilot selection,
not a claim of exact simple random sampling over all individual images.

Annotate the complete representative pilot. Choose one focal error per eligible
caption before generating any output. A focal error must be contradicted by
visible crop evidence, not merely absent from a COCO caption. Ambiguous errors
remain unverifiable. If no reliable repair is possible, retain the ordinary
conditions and record diagnostic ineligibility; do not silently drop the image.

A correction is a single contiguous replacement in the original caption.
The code preserves the prefix and suffix exactly. Human reviewers must confirm
that it corrects the intended focal claim and does not change unrelated content.
That semantic property is not established by span validation alone.

## Retrieval and leakage controls

The index contains exactly the Phase 2 approved 611,349 COCO captions belonging
to 122,204 images. Construction checks all eligible caption and parent-image IDs
against the approved identity lists and the frozen annotation ZIP. It excludes
all 1,000 shared NSD images plus 83 conservative potential-near-duplicate images.
The Phase 2 image screen is reused, not claimed to have been repeated here.

The baseline retriever is SQLite FTS5 BM25 with Porter/Unicode61 tokenization,
fixed stop words, OR-combined query terms, ascending BM25 score and caption-ID
tie-breaking. It retrieves captions, then prevents repeated donor image IDs or
identical normalized caption text within the selected top-k examples. A query
returns fewer examples if too few distinct matches exist; it does not invent
or silently replace missing results.

Distinct-donor selection begins with `max(100, 100 * top_k)` ranked caption
matches, then deterministically doubles that window when duplicate images or
caption texts would otherwise hide valid lower-ranked donors. Expansion stops
at top-k distinct results or exhausted matches. Both query variants use the
same policy and log their normalized query, window and expansion count.
Administrative chunk IDs, source-caption IDs and text hashes are stored as
metadata; they are neither indexed as text nor sent to the generator.

BM25 is a practical, reproducible CPU baseline. This implementation does not
establish behavior of dense-embedding or brain-feature retrieval. Generalizing
to all RAG systems would be unjustified. The neural feature files needed for a
separate brain-feature comparison have not been supplied or invented.

The original and repaired contexts are token-length matched where both are
nonempty. Prefix clipping can cut a final example; exact displayed excerpts,
full retrieved captions and truncation are recorded separately. The estimand
is the effect of the context actually supplied, including this frozen budget
policy. Zero-hit and unchanged-context cases are explicit diagnostics. Do not
post-select only cases where the intervention changed retrieval to estimate an
unconditional effect; a changed-context subgroup must be labelled secondary.

The review update explicitly counts partially displayed captions and retrieved
captions with no displayed text. The existing exact token-matching policy is
preserved; its possible loss of complete relations remains a limitation.

No target image, target reference caption, human label, NSD/COCO identity or
repair rationale enters the API request. The repaired query itself is not sent
in `rag_query_repaired`; only the retrieved context changes. Retrieved text
describes other images and is explicitly described as non-evidence about the
target. This conservative prompt is identical across generated conditions.

Shared meaning between different scenes is not itself identity leakage. Exact
target exclusion and the Phase 2 near-duplicate rule do not prove absence of
every edited duplicate, scene sequence or foundation-model pretraining overlap.

## Reproducibility and execution

The package pins the approved Phase 2 bytes, caption sources, model snapshot,
configuration, prompt, code digest, eligible corpus identities and database hash.
It logs retrieval scores, all context text, exact request bodies, raw responses,
provider request/model metadata and usage where supplied. API keys are never
written to logs. Response caching is scoped to source row, repeat and full
request body. Identical requests within that scope share an output; repeated
generations use different repeat keys. API output determinism is not guaranteed.
The plan and execution receipt also record Python, platform, SQLite and runtime
dependency versions.

Selection, random-context sampling and request order have deterministic seeds.
The hosted model does not receive an asserted reproducibility seed. The default
is one generation per condition for feasibility; more repeats require an
explicitly refrozen pilot and larger call/annotation budgets. Repeats never
increase the number of independent stimuli.

Paid execution requires `--execute`. Resumption skips completed requests.
The ledger records an attempt before networking. A timeout or interrupted
request remains an uncertain/billed-possibly attempt until deliberately retried.
There is no automatic retry, fallback model, fallback source caption or automatic
repair of malformed model output.

## Evaluation

Primary evidence is human judgment against the official displayed crop. Output
claims are atomized and labelled supported, contradicted or unverifiable.
The generator's own assessment is not used as ground truth. No automatic metric
is claimed to establish visual factuality.

For each baseline claim, record a transition. A contradicted claim can persist,
be explicitly corrected, be omitted, or remain unverifiable in the output. A
supported claim can be retained, contradicted, omitted or unverifiable. New
claims and attempted corrections are separately labelled against the image.

The primary focal-persistence point estimate uses adjudicable focal transitions.
Unverifiable transitions are also reported and contribute to lower/upper
persistence bounds; they are not silently counted as successful correction.
All-false-claim persistence bounds retain the baseline false-claim denominator.
Correct-claim retention and new false claims are mandatory companion outcomes.
The all-false-claim point estimate additionally reports its adjudicable claim
denominator. For paired condition differences, identification bounds use
`[lower_B - upper_A, upper_B - lower_A]`. These bounds quantify unresolved
transitions and are distinct from bootstrap confidence intervals for the
adjudicable point estimates. Subtracting two lower endpoints is not labelled
as a lower bound on the difference.

Outputs are blinded to condition and decoder in the local review interface.
Transition assessment necessarily exposes fixed baseline claims and their
labels. A single rater who also repaired queries is not fully independent or
fully blinded to the hypothesis. That is an operational-pilot limitation.
Independent output raters and adjudication are supported, and agreement is
computed on aligned baseline-claim transitions. Independently segmented output
claims are not assumed to share claim IDs for agreement calculations.

Identical output text for the same baseline row is reviewed once and mapped
back to its conditions/repeats. If the unchanged decoded baseline is judged
inconsistently with the frozen input claims, the analysis is blocked and the
disagreement is exported. Adjudicate the evidence; do not force labels to agree.
If the original truth labels or repair were wrong, invalidate the affected
pilot interpretation and retain an audit trail before creating revised inputs.

Metrics are exported per output with denominators. Repeats are averaged within
stimulus. Paired contrasts match the exact source row and repeat, separately
for each decoder, and bootstrap whole Phase 2 similarity groups. Fewer than
five independent clusters receive no confidence interval. A null metric means
undefined/no eligible evidence, not evidence of zero effect. Intervals are
exploratory and are not a power justification or multiplicity-adjusted test.

Ordinary-condition descriptive means cover the representative pilot; oracle
conditions cover only eligible repaired rows. Compare them using the paired
contrasts and their stated denominators, not by subtracting unmatched overall
means. Partial generation/review is explicitly recorded and cannot establish
an unbiased full-pilot effect by omission of failures.

## Results that would change the research direction

- Higher raw-RAG persistence without improved retention/utility would support
  investigating the proposed failure mechanism within this pipeline.
- Lower query-only persistence, with the original caption fixed, would support
  sensitivity to the retrieval-query intervention. It would not prove that an
  automatic query corrector can achieve the same effect.
- Equal context or equal persistence is a valid null result. Do not modify
  repairs, prompts or sampling after seeing outputs to manufacture a difference.
- Too few natural errors, unreliable labels, mostly identical retrieval,
  excessive truncation, API failures or loss of correct content may make the
  pilot inconclusive or the proposed short paper infeasible.

The Phase 3 deliverable is a runnable and audited pilot workflow plus its later
observations when you execute it. A confirmatory sample, statistical claims of
generality, and manuscript conclusions require a separate review.

## Offline retrieval representation diagnostic

The review command `retrieval-audit` samples eligible donor images, withholds
one caption per selected query image, and removes all whole-caption normalized
duplicates of those query texts before indexing. The remaining same-image
captions define one positive parent image for each query. This diagnostic never
uses NSD target references as queries, never reintroduces excluded images and
never calls a generation model. Source caption IDs and character spans stay
within one image in every representation.

It measures image-level Hits@1/3/10 and reciprocal rank, plus index size, runtime
and raw top-3 context length. The query/candidate pool, tokenizer, BM25 query,
ranking tie-breaks and image/text deduplication are shared across representations.
The longer text supplied by image bundles is explicitly reported. This is a
caption-to-caption retrieval proxy, not a controlled generation comparison or
evidence about persistent brain-decoding errors. Alternative representations
remain outside the production seven-condition runner pending review.
