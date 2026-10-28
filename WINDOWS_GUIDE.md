# Phase 3 execution guide for a Windows laptop

For the repository review update to version **0.1.1**, first follow
`review\LAPTOP_UPDATE.md`. The ZIP setup below describes the original delivered
package. Preserve any old frozen plans and outputs before applying the update;
the changed code digest intentionally prevents resuming them under new code.

This guide runs only the exploratory Phase 3 pilot. It does not train a decoder,
run a confirmatory study, or write scientific conclusions. Real experimental
generation has **not** been performed in the delivered project.

## 1. What you need

- Windows 10/11, 64-bit Python **3.12** and PowerShell. Python 3.13 is also allowed
  by the package; the local verification used Python 3.12 on Linux. A native
  Windows execution of the review patch has not been claimed. The original
  repository commit passed Windows/Linux CI on Python 3.12 and 3.13; see the
  separate review report for the exact run and scope of this evidence.
- A normal CPU. **No GPU, CUDA, PyTorch, fMRI beta volumes or model training is
  required.** An 8 GB RAM laptop is a practical recommendation, not a measured
  minimum. Allow roughly 2 GB free disk space for the environment, metadata,
  annotation ZIP and SQLite index; no 20 GB COCO image download is needed.
- Internet for package installation and downloading approximately 253 MB of
  COCO annotations, small pinned caption files and the selected official crops.
  The public tokenizer table is included for offline token counting after setup.
- Your completed NSD access agreement. The configuration records the approval
  you already supplied. This is not permission to redistribute NSD photographs.
- For paid generation only: an API account with access to the configured model,
  an API key and API billing. The local stages need no API key.
- Human time to inspect images, label claims and verify minimal repairs, then
  review model outputs. The datasets do **not** contain these judgments.

Install 64-bit Python from [python.org](https://www.python.org/downloads/windows/),
including the Python launcher. Check available versions:

```powershell
py --list
py -3.12 --version
```

Use `py -3.13` in the environment-creation command if you deliberately choose
Python 3.13. Do not use Python 3.14 or a 32-bit interpreter with this release.

## 2. Extract and install

Download `Brain-Imager_Phase-3_Windows_2026-10-28.zip`. The archive contains one
top-level `brain_imager_phase3` folder. In PowerShell:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Projects" | Out-Null
Expand-Archive -Path "$env:USERPROFILE\Downloads\Brain-Imager_Phase-3_Windows_2026-10-28.zip" -DestinationPath "$env:USERPROFILE\Projects"
$Project = Join-Path $env:USERPROFILE "Projects\brain_imager_phase3"
Set-Location $Project
py -3.12 -m venv .venv
$Py = Join-Path $Project ".venv\Scripts\python.exe"
& $Py -m pip install -r requirements-lock.txt
& $Py -m pip install -e . --no-deps --no-build-isolation
& $Py -m pytest -q
& $Py -m brain_imager_phase3 doctor
```

Stop if installation or tests fail. `doctor` reports versions, SQLite FTS5,
paths and whether a key exists; it never displays the key or calls the API.
The tests use synthetic fixtures and mocked responses, not paid model requests.

Activation is optional because every command above names the virtual-environment
interpreter explicitly. If you prefer activation:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, continue using `& $Py`; changing the machine's
execution policy is unnecessary. `Setup.ps1` is an optional convenience equivalent
to the installation/test commands, when local script execution is allowed.

## 3. Configure the pilot before freezing identities

Open `config\pilot.json` in a text editor. Defaults are:

| Setting | Default |
|---|---|
| Decoder | `umbrae`, the original Phase 2 variant |
| Distinct pilot stimuli | 20 |
| Repeats | 1 |
| Retrieval | SQLite FTS5 BM25, top 3 distinct donor images/caption texts |
| Context budget | 240 tokens under the declared `o200k_base` tokenizer |
| Generator | `gpt-5.4-mini-2026-03-17` |
| Maximum completion tokens | 256 |
| Maximum API attempts | 150, including failed/uncertain attempts |
| Maximum estimated cost reservation | USD 2.00 |

For an even smaller first pilot, change `pilot_size` to 5 **before** the next
step. You can do it without manually editing JSON:

```powershell
$Cfg = Join-Path $Project "config\pilot.json"
$Settings = Get-Content $Cfg -Raw | ConvertFrom-Json
# Optional: uncomment the next line for a 5-stimulus first pilot.
# $Settings.pilot_size = 5
$Settings | ConvertTo-Json -Depth 20 | Set-Content $Cfg -Encoding UTF8
$Work = Join-Path $Project $Settings.workspace
```

The loader accepts PowerShell's UTF-8 BOM. Do not put credentials in this file.
The defaults preserve one named decoder. Adding decoders or repeats multiplies
work and calls; it also requires a separately frozen configuration and budget.
After selection/planning, do not change settings in the same workspace.

## 4. Recover and validate the approved inputs

```powershell
& $Py -m brain_imager_phase3 --config $Cfg init
& $Py -m brain_imager_phase3 --config $Cfg fetch --what captions
& $Py -m brain_imager_phase3 --config $Cfg fetch --what coco
& $Py -m brain_imager_phase3 --config $Cfg pilot
& $Py -m brain_imager_phase3 --config $Cfg fetch --what crops
& $Py -m brain_imager_phase3 --config $Cfg index
& $Py -m brain_imager_phase3 --config $Cfg validate
& $Py -m brain_imager_phase3 --config $Cfg validate --deep
```

Expected checks: 2,946 verified caption rows, 982 original sample identities,
122,204 eligible corpus images and 611,349 indexed captions. Your pilot contains
the configured number of distinct stimuli, with Phase 2 similarity groups kept
together. Sampling happens before error labels or model outputs are available.

`init` verifies the exact bundled Phase 2 ZIP and its member checksums. Fetching
captions verifies pinned source bytes and row hashes. The index excludes all
1,083 Phase 2 excluded images and every caption attached to them. It checks the
entire eligible-caption ID set, rather than trusting counts alone. Downloads are
reused only after their integrity checks. Interrupted `.part` downloads restart.

The selected crops are the official 425×425 NSD PNGs. For crops outside the
earlier 20-image check, this step records newly acquired official bytes and
their hashes; it does not pretend they were already pixel-checked in Phase 2.

No decoder, embedding API, LLM or RAG-generation experiment runs in this step.
`Prepare-Data.ps1` combines these local preparation commands using the default
configuration, including creation of the first annotation template.

## 5. Supply the missing human evidence

```powershell
& $Py -m brain_imager_phase3 --config $Cfg make-pre --rater R1
& $Py -m brain_imager_phase3 --config $Cfg annotate --mode pre --file "$Work\pilot\annotations\pre_R1.jsonl"
```

The command opens a local page at `127.0.0.1`. If it does not open automatically,
copy the exact URL printed in the terminal. The page shows the displayed crop
and the frozen decoded caption. It does not call an API.

For **every** pilot row:

1. Select source-caption text and add atomic claims. Label each as supported,
   contradicted or unverifiable, with type and visual evidence.
2. If there is a clear error, select **one focal contradicted claim** before
   viewing generated outputs. Choose a contiguous edit span, enter its minimal
   factual replacement and explain the visible evidence. Verify the repair.
3. Preserve all non-focal wording. The program constructs the repaired query
   from the span; it does not allow an unrelated rewritten query as a substitute.
4. If no clear error exists, leave the focal claim empty. If errors exist but a
   reliable minimal correction is impossible, explain the diagnostic exclusion.
5. Mark claim coverage and review complete; click **Save this record**.

See `ANNOTATION_GUIDE.md` for the complete rules. These templates have no
pre-filled truth labels. A valid JSON record is not proof that its labels are
scientifically correct; image-grounded human judgment remains necessary.

Press Ctrl+C in the terminal after saving to close the local annotation server.
Then freeze the reviewed inputs:

```powershell
& $Py -m brain_imager_phase3 --config $Cfg freeze-inputs --annotations "$Work\pilot\annotations\pre_R1.jsonl" --annotation-policy single_rater_pilot
```

For a genuinely adjudicated input file use `--annotation-policy adjudicated_pilot`
and point to that file. The program records your declared policy; it cannot
certify that two independent people performed the work.

Incomplete reviews, wrong crop/caption hashes, unverifiable focal errors,
unrelated edits and unverified repairs block planning. Do not invent labels to
bypass this gate. Do not revise a focal repair after seeing model outputs.

## 6. Build and inspect the experiment plan — still no paid calls

```powershell
& $Py -m brain_imager_phase3 --config $Cfg plan
& $Py -m brain_imager_phase3 --config $Cfg run
Get-Content "$Work\pilot\retrieval_diagnostics.jsonl" -TotalCount 3
```

`plan.json` freezes every condition, prompt, request body, source-caption identity,
retrieved document, random-context seed and cost reservation. The default
`run` command is preview-only. It does not instantiate an API client.

The main comparison is `rag_query_repaired` versus `rag_original`. In both,
the generator's source caption is the **same original erroneous caption**.
Only context obtained from the query changes. The two other repaired conditions
complete the earlier 2×2 design. Oracle conditions apply only to eligible focal
error rows; ordinary conditions run on the full representative pilot.

Where both queries retrieve context, the raw and repaired contexts are clipped
to a common token count. If one query has zero hits, that exception is logged,
not hidden by inventing examples. The random control matches the original
displayed-context length. Full retrieval lists and exactly displayed excerpts
are logged separately, including truncation and token counts.

The request body contains only the source caption and other-image examples.
It does not contain the repaired query itself in the query-only condition,
the target image, reference captions, IDs, human labels or repair rationale.

## 7. Costs and model availability

The official model page checked on 28 October 2026 lists GPT-5.4 mini text pricing
of **USD 0.75 per million input tokens and USD 4.50 per million output tokens**:
[official model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini).
Verify current prices and your account's model access before execution.

For 20 stimuli, one decoder and one repeat, the design requests at most 120
unique generation calls before identical-prompt reuse; it can be fewer because
oracle conditions require focal errors and identical requests are cached.
For illustration only, 120 calls averaging 1,000 input and 256 output tokens
would cost approximately **USD 0.23**, before discounts, taxes or other account
charges. This is not a measured pilot cost or a guarantee.

The code defaults to a USD 2 **estimated reservation limit**, 150 total attempts,
and two attempts per distinct request. Failed or uncertain attempts consume the
reservation. These are client-side controls, not a provider-enforced dollar cap.
Use account-level spending controls too. The final provider bill is authoritative.
No provider tools, search, vision calls or embeddings are enabled.

The default model is a pinned snapshot, not an alias. If unavailable, the program
stops. Do not silently substitute a different model mid-run. Choose an available
model deliberately, verify its supported parameters/pricing, and freeze a new
pilot configuration; this release was documented for the default provider.
The returned model identifier must match the configured snapshot exactly.

## 8. Configure your API key and explicitly execute

Read the key without putting it in shell history or a configuration file:

```powershell
$Secret = Read-Host "OpenAI API key" -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $Secret).Password
Remove-Variable Secret
```

Optional one-request connectivity check using the **already frozen pilot plan**:

```powershell
& $Py -m brain_imager_phase3 --config $Cfg run --execute --max-calls 1
```

That command is a real paid call if the provider accepts it. It is part of the
same pilot and is cached. Resume the remaining planned requests with:

```powershell
& $Py -m brain_imager_phase3 --config $Cfg run --execute
```

Keep the terminal open. There are no automatic retries or model fallbacks.
Successful requests are persisted. Running the same command again reuses
completed requests. Identical prompts within the same source row and repeat
share one response, preventing an artificial difference when the query
intervention produced identical context. Different repeats have different cache
keys. Hosted-model responses are not guaranteed bitwise deterministic; no API
seed support is claimed. Selection, random controls and execution order are seeded.

After a timeout, rate-limit or other failure, inspect the receipt and your provider
usage first. A timeout may have been billed even if its result was not received.
Only then deliberately retry:

```powershell
Get-Content "$Work\pilot\execution_receipt.json"
& $Py -m brain_imager_phase3 --config $Cfg run --execute --retry-failed
```

Remove the key from this PowerShell session when finished:

```powershell
Remove-Item Env:\OPENAI_API_KEY
```

Do not treat `outputs.jsonl` as a result table until human evaluation is complete.
Failed, refused and incomplete outputs remain failures; the code never replaces
them with the original caption and counts that as successful generation.

## 9. Review generated captions, blinded to condition

```powershell
& $Py -m brain_imager_phase3 --config $Cfg make-review --rater R1
& $Py -m brain_imager_phase3 --config $Cfg annotate --mode post --file "$Work\pilot\annotations\post_R1.jsonl"
```

The interface hides condition, decoder variant and query repair. It first shows
the output and image for atomic-claim labeling, then the fixed baseline claims
for transition assessment. Transition assessment is not blinded to those baseline
claims. Identical output text for the same baseline row is reviewed once and
mapped back to all corresponding conditions/repeats.

Label newly introduced and attempted-correction claims as well as retained
claims. A false attempted correction is a new false claim. Explicit correction
requires a supported replacement claim; omission is scored separately. Save all
records before Ctrl+C.

For an independent second reviewer:

```powershell
& $Py -m brain_imager_phase3 --config $Cfg make-review --rater R2
& $Py -m brain_imager_phase3 --config $Cfg annotate --mode post --file "$Work\pilot\annotations\post_R2.jsonl"
& $Py -m brain_imager_phase3 --config $Cfg compare-raters --a "$Work\pilot\annotations\post_R1.jsonl" --b "$Work\pilot\annotations\post_R2.jsonl"
```

Use genuinely independent reviewers; changing a rater ID does not create
independence. Share the local annotation interface, not `plan.json` or the
`private\review_key.jsonl` file. For remote raters, do not expose this local server
to the internet; arrange an authorized local copy and data access separately.

The agreement file identifies transition disagreements. For adjudication, make
a named copy of one review file, adjudicate discrepancies against the crop and
the other review, and record the adjudicator in `annotator_id`/notes. The program
does not automatically turn agreement into ground truth.

## 10. Produce the Phase 3 evaluation outputs

For a single-rater operational pilot:

```powershell
& $Py -m brain_imager_phase3 --config $Cfg evaluate --review "$Work\pilot\annotations\post_R1.jsonl" --bootstrap 2000
```

If you created an adjudicated file, use its path instead. Evaluation requires
complete labels for every exported review task. It reports error persistence,
correction, omission, correct-claim retention, new false/unverifiable claims,
output length, denominators and paired contrasts. Repeats are averaged within
stimulus and Phase 2 similarity groups are resampled together. Undefined
outcomes remain null; small cluster counts do not receive invented intervals.

Only use `make-review --allow-partial-review` when deliberately documenting
generation attrition. Its missing jobs are recorded, and any available-case
analysis must be interpreted accordingly. Prefer completing the planned pilot.

This command produces exploratory estimates, not acceptance of a hypothesis,
proof of novelty, a confirmatory analysis or paper conclusions. Stop after the
Phase 3 evidence and feasibility review.

## Output locations

All paths below are relative to `$Work` (normally `workspace`).

| Path | Contents |
|---|---|
| `phase2\` | Unmodified approved audit package contents |
| `captions\` | Hash-verified cached decoder captions |
| `downloads\annotations_trainval2017.zip` | Official COCO annotations |
| `crops\` | Official pilot crops and individual download receipts |
| `corpus.sqlite3`, `corpus_manifest.json` | Sealed BM25 index and provenance |
| `pilot\selection.json` | Frozen pilot and reserved stimulus identities |
| `pilot\annotations\` | Your pre- and post-generation human judgments |
| `pilot\frozen_pre_annotations.json` | Immutable repaired-query inputs |
| `pilot\plan.json` | All planned conditions and exact request bodies |
| `pilot\retrieval_contexts.jsonl` | Retrieved IDs, scores, captions and displayed excerpts |
| `pilot\retrieval_diagnostics.jsonl` | Context changes, overlaps, truncation and zero-hit cases |
| `pilot\run.sqlite3` | Durable request, retry and cost ledger |
| `pilot\requests\`, `pilot\responses\` | Exact model requests/responses; no API keys |
| `pilot\outputs.jsonl` | Outputs and failures with stimulus/decoder identities |
| `pilot\execution_receipt.json` | Calls, cost reservations and generation status |
| `pilot\review_tasks.jsonl` | Blinded, deduplicated human-review tasks |
| `pilot\private\review_key.jsonl` | Condition mapping; withhold from raters |
| `pilot\evaluation\pilot_summary.json` | Exploratory metrics and paired contrasts |
| `pilot\evaluation\row_metrics.csv` | Per-output metrics, UTF-8 BOM for Excel |

## Troubleshooting

| Symptom | Action |
|---|---|
| `py` not recognized | Install the Python launcher, reopen PowerShell, or use the installed Python executable's full path to create the venv. |
| Activation blocked | Use `& $Py` commands; activation is optional. |
| No matching wheel / compiler requested | Check 64-bit Python 3.12 and the pinned requirements. Do not install CUDA or unrelated compiler stacks as a workaround. |
| `No module named brain_imager_phase3` | Run the editable-install command with the same `$Py`; confirm you are in the project directory. |
| SQLite `no such module: fts5` | Use the official Windows Python distribution and rerun `doctor`; do not silently switch retrieval implementations. |
| Download timeout/503 | Rerun the same `fetch` command. It verifies existing completed files and restarts `.part` files. No alternative dataset is substituted. |
| SHA-256 mismatch | Stop. Preserve the mismatching file for inspection; compare with the approved manifest. Do not update expected hashes to force a pass. |
| Existing crop has no trusted receipt | Move that unverified PNG aside, then fetch the official image. A filename and size alone are insufficient. |
| `frozen_pre_annotations.json` missing | Complete and freeze the human input annotations; do not fabricate replacements. |
| Incomplete claim/repair validation | Save a draft, correct the stated fields in the annotation UI, then mark complete and save again. |
| Port 8765 in use | Add `--port 8766` to `annotate`; open the newly printed URL. |
| Model HTTP 401 / 403 | Check key, billing and account access. Do not send your key to another person or place it in the project. |
| HTTP 404 / unsupported parameter | Check the pinned model and official API documentation. Freeze any model/config change as a new pilot. |
| HTTP 429 | Check quota/rate limits, wait as appropriate, inspect usage, then explicitly retry. There is no hidden retry loop. |
| Timeout / interrupted call | Billing outcome can be unknown. Inspect ledger/provider usage before `--retry-failed`. |
| `execution.lock` exists | Ensure no run is active. Only then remove a stale `$Work\pilot\execution.lock`; the ledger still protects uncertain requests. |
| Config/code/plan changed | Restore the frozen version or create a separately named workspace. Do not merge outputs across protocols. |
| Corrected query retrieves the same context | This is a valid null intervention, recorded in diagnostics. Do not edit the repair after seeing outputs to force a difference. |
| No focal errors in the pilot | Ordinary comparisons remain available, but the query-repair hypothesis is not testable in this sample. Report that limitation. |
| API calls complete but no factuality metrics | Complete post-generation human review and run `evaluate`. A model-generated caption is not a truth label. |
| Unchanged-baseline review disagrees with frozen input | Inspect `evaluation\baseline_annotation_disagreements.json` and adjudicate against the crop. Do not force labels to agree; if the original input evidence was wrong, preserve the audit and invalidate that interpretation before starting revised inputs. |

Official references: [Python venv](https://docs.python.org/3.12/library/venv.html),
[SQLite FTS5/BM25](https://www.sqlite.org/fts5.html),
[Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
[GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini).
