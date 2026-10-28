# Human annotation guide

No ground-truth claim labels or corrected queries are provided by NSD, COCO or
the decoder-caption files. These judgments must be made against the **official
displayed NSD crop**, using the local interface.

## Before generation

An atomic claim should be independently assessable: object presence, attribute,
count, action, relation or scene. Split a sentence containing several assertions
into separate propositions. Do not automatically treat every noun or every word
as a claim. Record the relevant source-caption character span and a concise
proposition. UI selection indices are converted to Python Unicode code-point
indices; the end position is exclusive.

| Label | Use |
|---|---|
| `supported` | The displayed crop supports the proposition at the stated specificity. |
| `contradicted` | Visible evidence contradicts it; for example a clearly different object, count or relation. |
| `unverifiable` | The crop does not permit a reliable decision, including hidden details, ambiguity or knowledge not visually available. |

Absence from the human COCO references is not contradiction. An object cropped
out of NSD may appear in a COCO caption; evaluate the crop. Conversely, mere
non-visibility may be unverifiable rather than proof of absence. Do not infer
identities, intentions, occupations or hidden actions from stereotypes.

Annotate all claims in every selected caption, including captions without clear
errors. The complete-coverage checkbox is your declaration, not an automated
proof. Retain the displayed evidence or reason for uncertainty in each record.

Choose one clearly contradicted focal claim before seeing model outputs. Make
one minimal contiguous replacement that corrects that claim. Keep all other
wording unchanged. The replacement must be an explicit repair rather than an
empty deletion, and must overlap the focal span. Confirm that the repaired
query is supported at that point and has not introduced an unrelated fact.

If the correction is ambiguous or would require substantial unrelated edits,
record diagnostic ineligibility rather than invent a repair. Other ordinary
conditions still use the caption. If no contradicted claim exists, leave focal
claim and query edit empty. Select an error by a consistent rule, for example
the first clear contradicted proposition in caption order, and record that rule
before annotation; do not choose whichever later yields the strongest result.

## After generation

First atomize and label the output independently against the crop. Then assess
its relation to the frozen baseline claims. Conditions and decoder names are
hidden, but the transition task exposes baseline claims. Avoid opening private
mapping or retrieval files while performing blinded output labeling.

Every output claim has an origin:

- `baseline`: a retained/re-expressed baseline assertion or its altered form;
  link it to the appropriate baseline claim.
- `correction`: a proposed replacement for a baseline assertion; link it to
  that claim. This describes its role, **not** whether it is true. Label a false
  attempted correction as contradicted. It counts as a newly introduced error.
- `new`: a claim not linked to a baseline assertion. Leave the baseline link empty.

For a baseline **contradicted** claim:

| Transition | Meaning |
|---|---|
| `persisted` | The same incorrect proposition remains asserted, including a paraphrase. |
| `corrected` | A supported replacement is explicitly stated. Add that supported `correction` claim to the output inventory and link it. |
| `omitted` | The original false proposition is no longer asserted and no supported explicit correction is established. A false replacement is separately counted as a new error. |
| `unverifiable` | The output is too ambiguous to determine the transition reliably. |

For a baseline **supported** claim, use `retained`, `contradicted`, `omitted` or
`unverifiable`. For an initially unverifiable claim, use `retained`, `omitted`
or `unverifiable`; these do not enter the verified-false or verified-true
denominators. Unsupported details and indeterminate transitions are not
automatically false or successful corrections.

If the output is meta-commentary/refusal rather than an image caption, mark it
unusable and still label any actual visual claims it makes. A successful API
refusal/truncation is already kept out of completed outputs by the runner.
Do not label an empty output inventory as a usable caption.

The validator checks identity, completeness flags, spans, label enums and
internal links. It cannot prove semantic correctness or discover missing claims.
If unchanged-baseline labels contradict the frozen input labels, adjudicate the
evidence. Do not change a judgment merely to pass validation. A mistaken input
repair can invalidate the scientific comparison.

## Independent review and adjudication

For a feasible operational pilot, one reviewer may annotate with the policy
`single_rater_pilot`. Report that limitation. For stronger evidence, have a
different reviewer label outputs independently and use a second output rater.
Rater IDs must represent actual reviewers; do not manufacture independence.

Create `post_R2.jsonl` through `make-review` so it starts blank. Compare completed
files with `compare-raters`; inspect disagreements against the crop. Copy an
original review file to a new adjudicated filename before editing it, retain
both independent originals, and record the adjudicator and rationale. Use the
adjudicated file for evaluation. Cohen's kappa is reported only for the aligned
baseline transitions; output claim segmentation can differ between reviewers.

Identical text for the same source row is reviewed once. Its judgment is reused
across conditions/repeats rather than treated as additional independent evidence.
Human confidence, disagreement and unresolved ambiguity should remain visible
in the pilot report.
