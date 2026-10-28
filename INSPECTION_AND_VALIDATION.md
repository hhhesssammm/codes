# Phase 3 inspection and validation record

Date: **28 October 2026**. This records completed implementation checks, not
experimental findings. No real generation request was made and no human truth
labels, query repairs, model outputs or scientific results were invented.

## Recovered project inputs

The previously prepared large working directory was absent in this session.
The approved Phase 2 reproducibility ZIP was recovered, hash-checked and
extracted. The delivered copy is byte-identical to that approved release.
Paths below are relative to the extracted Phase 3 project root; `workspace/`
is created by the commands in `WINDOWS_GUIDE.md` and is not bundled.

| Asset | Actual path / format | Check and result |
|---|---|---|
| Approved Phase 2 release | `assets/Brain-Imager_Phase-2_reproducibility_2026-10-28.zip`, 21,872,584 bytes | Exact archive SHA-256 and all member checksums passed; 45 members. |
| Caption alignment | `workspace/phase2/results/alignment_manifest.jsonl` | 2,946 rows, unique manifest keys; 982 rows per named decoder; hashes and joins to the approved sample manifest passed. |
| Sample identity | `workspace/phase2/results/sample_manifest.jsonl` | 982 distinct sample, zero-based NSD and COCO image identities; no count-based reassignment or guessed ordering. |
| Cached caption sources | `workspace/captions/`, four JSON files | Pinned BrainHub bytes and Git blob hashes checked; keys exactly `0` through `981` in order; all 2,946 decoded-caption UTF-8 hashes matched. The fourth file contains reference captions, never generator evidence. |
| Corpus eligibility | `workspace/phase2/results/eligible_coco_*_ids.txt`, exclusions JSONL | Exact approved identity files; targets contained in exclusions; eligible/excluded sets disjoint. |
| COCO annotations | `workspace/downloads/annotations_trainval2017.zip`, 252,907,541 bytes | Fresh official download matched the Phase 2 SHA-256. Only caption annotations are indexed. |
| Retrieval database | `workspace/corpus.sqlite3`, SQLite FTS5 | Actually built: 611,349 captions belonging to 122,204 images. Construction matched the complete approved caption and parent-image sets; database and FTS integrity checks passed. |
| Exclusions | `workspace/phase2/results/retrieval_exclusions.jsonl` | All 1,083 excluded images remain excluded: 1,000 shared NSD images plus 83 conservatively flagged possible near-duplicates. The latter are not relabelled as confirmed duplicates. |
| Pilot identities | `workspace/pilot/selection.json` | Deterministic selection of 20 stimuli using whole Phase 2 similarity groups; chosen before annotations or outputs. |
| Pilot displayed crops | `workspace/crops/*.png` and receipt JSON files | 20 official PNG downloads decoded successfully at 425×425 pixels; URL, identity and new byte hashes recorded. All 20 are outside the earlier Phase 2 crop-check subset. No new human visual QA is claimed. |
| Human input template | `workspace/pilot/annotations/pre_R1.jsonl` | 20 blank review records created. No factuality labels or repairs completed. |

The Phase 2 evidence already includes its broader identity and image checks.
This implementation reuses that approved evidence; it does not claim to have
rerun the decoder, trial alignment or the full COCO near-duplicate screen.

## Important hashes and revisions

| Item | SHA-256 / revision |
|---|---|
| Approved Phase 2 ZIP | `f03a3b653c94dbda169996f48f5dfd001e24c1398457e3eed4943a817df12c25` |
| Alignment manifest | `7cc41361c032146d42a65e12ed8623edf8e0ce282af18bb7fb060daf491f93c5` |
| Sample manifest | `915020aaa374bf526c672982daf25d6a64a79f2249d411a9863c871e77ce4677` |
| Official annotation ZIP | `113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268` |
| Database built in this environment | `42a4cdd11c551649e9c2bbaee2cd466957f892d1515150ab4aa3ab990182a60f` |
| BrainHub caption revision | `4838666f1a04d0521c2184fa50b5b77e7e7ac5ee` |
| Phase 2 UMBRAE exporter revision | `8c1795c434a41cdd38ce6628b7e1a774f31d9483` |
| Phase 2 Hugging Face NSD revision | `421fb80ea4ca5600c7364ed400f9a5941380c387` |
| Phase 2 image-cache revision | `77d4f8e1c1d6d417a363ac32c380f12924bd92c8` |

SQLite versions may produce different database bytes on another machine. The
program builds from the pinned annotation source and complete approved identity
sets, records that machine's database hash and then freezes it for that run.
The table's database hash is an observation, not a required cross-platform hash.

The reproducibly selected COCO image IDs with default settings were:
`191740, 354045, 38801, 174213, 477852, 323182, 186828, 58407, 246166, 281567,
150196, 151307, 377576, 221441, 336374, 268008, 539395, 372959, 330086, 106107`.
Changing the configuration requires a separate frozen workspace.

## Installation and software checks

- Created a clean Python 3.12 virtual environment, installed every pinned
  requirement, installed the project in editable mode and ran `pip check`:
  **no broken requirements**.
- Environment: Linux, 64-bit Python 3.12.14, SQLite 3.53.1 with FTS5, HTTPX
  0.28.1, tiktoken 0.12.0, Pillow 12.3.0, pytest 8.4.2.
- Final automated suite: **46 passed**, including a synthetic end-to-end
  experiment with a mock provider. The JUnit evidence is included under
  `validation/`. Synthetic captions and output judgments are test fixtures,
  not observations about the real pilot.
- Tests cover corrupted/missing assets, duplicate identities, leaked donors,
  BM25 ordering, token budgets, minimal-edit validation, the unchanged source
  caption in the query-only cell, full factorial conditions, request reuse,
  explicit retries and cost limits, malformed/refused API responses, missing
  evaluations, baseline disagreements, cluster-level inference and the local
  annotation server's access and immutable-field controls.
- Python compilation and the annotation UI JavaScript syntax check passed.
- Windows CPython 3.12 compatible wheels were downloaded for the full locked
  dependency set, including Windows-only Colorama: 21 wheels. No compiler,
  CUDA or GPU package is required by this dependency set.
- **No native Windows/PowerShell runtime test was possible here.** The Windows
  CI workflow is included but has not been executed. Passing Linux tests and
  resolving Windows wheels do not establish native Windows execution.
- **No live model endpoint was tested.** API request structure was checked
  against official documentation and HTTP behavior tested with mocked
  responses. Account/model access must be checked on the user's machine.

Running `plan` against the real prepared inputs stopped with exit code 2 and
the specific missing asset `workspace/pilot/frozen_pre_annotations.json`.
This is the intended gate: verified human claim labels and minimal repairs must
exist before creating the generation plan. It is not a software test failure.

## Materials still required

1. Completed image-grounded baseline claim labels, focal-error selection and
   minimal query repairs, with a declared single-rater or adjudicated policy.
2. An API account/key with access to the pinned model if paid generation is
   selected. No credential is included or needed for setup/data preparation.
3. Human post-generation claim and transition judgments; preferably independent
   review and adjudication for evidence beyond an operational pilot.

Historical Brain-Imager pre/post-rewrite pairs and original decoder checkpoint
hashes remain unavailable. They were not recreated or inferred. The supported
route is the approved named public cached decoder outputs, with one subject and
stimulus-level observations. No trial-level independence is claimed.

## Release boundaries

The ZIP includes source, configurations, locked dependencies, tests, guides,
the approved Phase 2 audit ZIP and a public tokenizer cache. It omits the
downloaded COCO ZIP, retrieval database, NSD photographs, generated workspaces,
credentials and local virtual environments. Setup commands recover authorized
public inputs and verify their hashes. Keep data access and upstream terms.

The code is ready for local setup and human annotation. The scientific pilot is
**not complete**, and the existence of enough natural focal errors remains an
empirical question. No Phase 4 study or manuscript conclusions are supplied.
