# Apply and verify the repository review on Windows

This update targets **only** commit
`b9cc9aa00a6f7e4787d30f2fbcbd43af95edc9bc` of
https://github.com/hhhesssammm/codes. The remote repository was not changed:
the connected account had read access but no push permission. `git pull` alone
will therefore not obtain these fixes. Apply the supplied patch below.

The recommended route uses a separate clone and new workspace. It preserves
your existing source, human annotations, plans, output files and data. Do not
delete or overwrite those files. Changed code hashes intentionally prevent
resuming old frozen experiment plans under this version.

All commands in this guide are local checks, preparation or CPU-only retrieval
diagnostics. **No API key, GPU, decoder training or generation call is needed.**
The seven production conditions, model configuration, seeds and dependencies
are unchanged. Do not execute a paid pilot as part of this review.

## 1. Prerequisites and unpacking

Use Windows 10/11, Git for Windows, and 64-bit Python 3.12 with the Python
launcher. Python 3.13 is supported by the package; the updated local tests used
3.12 on Linux. Obtain Python from https://www.python.org/downloads/windows/
and Git from https://git-scm.com/downloads/win if needed. An 8 GB laptop is a
practical recommendation, not a measured minimum. Allow roughly 2 GB free
disk plus any second copy of your existing inputs. Deep validation temporarily
loads the index and annotation data in memory. Close other large applications
if memory is tight; do not skip a failing validation.

Download `Brain-Imager_RAG_Review_2026-10-28.zip` to Downloads. Open PowerShell
and run the blocks in order, in the same terminal. Adjust the ZIP path only if
your browser saved it elsewhere.

```powershell
$ErrorActionPreference = "Stop"
function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Exe failed with exit code $LASTEXITCODE. Stop and inspect the error."
    }
}
Invoke-Checked "git" @("--version")
Invoke-Checked "py" @("-3.12", "--version")
$Bundle = Join-Path $env:USERPROFILE "Downloads\Brain-Imager_RAG_Review_2026-10-28.zip"
$Review = Join-Path $env:USERPROFILE "Downloads\Brain-Imager_RAG_Review_2026-10-28"
if (Test-Path $Review) { throw "Review destination already exists; choose a new empty path." }
Expand-Archive -LiteralPath $Bundle -DestinationPath $Review
$Patch = Join-Path $Review "brain_imager_review.patch"
if (!(Test-Path $Patch)) { throw "Patch is missing from the extracted bundle." }
```

`Invoke-Checked` explicitly stops on failed native commands: PowerShell's
`$ErrorActionPreference` alone does not reliably do that for Git/Python.
Activation and changes to execution policy are unnecessary.

## 2. Synchronize the exact base and apply the patch

```powershell
$Projects = Join-Path $env:USERPROFILE "Projects"
New-Item -ItemType Directory -Force $Projects | Out-Null
$Project = Join-Path $Projects "codes-reviewed-20261028"
if (Test-Path $Project) { throw "Project path already exists; choose a new empty directory." }
Invoke-Checked "git" @("-c", "core.autocrlf=false", "clone", "https://github.com/hhhesssammm/codes.git", $Project)
Set-Location $Project
Invoke-Checked "git" @("config", "core.autocrlf", "false")
$Base = "b9cc9aa00a6f7e4787d30f2fbcbd43af95edc9bc"
Invoke-Checked "git" @("switch", "-c", "review/rag-integrity-20261028", $Base)
Invoke-Checked "git" @("apply", "--check", $Patch)
Invoke-Checked "git" @("apply", $Patch)
Invoke-Checked "git" @("diff", "--check")
Invoke-Checked "git" @("status", "--short")
Invoke-Checked "py" @("-3.12", "verify_release.py")
```

The verifier must report `PASS`. It checks all declared release files including
the unchanged Phase 2 ZIP and tokenizer table. Run it **before** editing any
tracked configuration. `.gitattributes` keeps text in LF form on Windows so
byte hashes remain reproducible. These checks detect incomplete application or
changed files; a checksum file is not a cryptographic publisher signature.

Every changed file and its **Add/Replace** action is listed in
`review\CHANGELOG_FILES.md`. `git apply` performs those actions automatically;
do not manually replace selected modules while leaving the rest at the old
version. `git diff --stat` omits untracked added files until staged, so also use
`git status --short` when inspecting the change.

If you prefer your existing clone, first save your own work, confirm that
`git status --porcelain` is empty and that `git rev-parse HEAD` equals `$Base`,
then create a new local branch and perform the same `git apply --check` step.
If either precondition fails, use the separate-clone route above. Do not use
`reset --hard`, `clean`, forced patch application or whitespace-ignoring options
to conceal conflicts. A CRLF-related patch failure is best resolved by the fresh
clone with `core.autocrlf=false`, leaving your old checkout intact.

## 3. Install the unchanged dependency set and run tests

```powershell
Invoke-Checked "py" @("-3.12", "-m", "venv", ".venv")
$Py = Join-Path $Project ".venv\Scripts\python.exe"
Invoke-Checked $Py @("-m", "pip", "install", "-r", "requirements-lock.txt")
Invoke-Checked $Py @("-m", "pip", "install", "-e", ".", "--no-deps", "--no-build-isolation")
Invoke-Checked $Py @("-m", "pip", "check")
New-Item -ItemType Directory -Force "$Project\workspace\review_checks" | Out-Null
Invoke-Checked $Py @("-m", "pytest", "-q", "--junitxml=workspace/review_checks/laptop_tests.xml")
Invoke-Checked $Py @("-m", "brain_imager_phase3", "doctor")
```

Expected: **71 passing tests**, no dependency conflicts, package version
**0.1.1**, 64-bit Python and `fts5_available: true`. Tests use synthetic fixtures
and mocked provider responses; passing tests is not an experimental result.
The API-key-present flag may be true if you already set one; `doctor` does not
call the provider. The supplied historical `review\validation\reproduced_regressions.xml`
deliberately records seven failures **before** fixes; it is not a failing result
from the updated suite.

## 4. Create a separate review workspace and reuse verified inputs

Create an ignored local configuration without editing the shipped default:

```powershell
$Cfg = Join-Path $Project "config\local-review.json"
if (Test-Path $Cfg) { throw "Local review config already exists; inspect it before proceeding." }
$Settings = Get-Content "$Project\config\pilot.json" -Raw | ConvertFrom-Json
$Settings.workspace = "workspace/review-20261028"
$Settings | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $Cfg -Encoding UTF8
$Work = Join-Path $Project $Settings.workspace
if (Test-Path $Work) { throw "Review workspace already exists; preserve it and choose a new path." }
New-Item -ItemType Directory -Path $Work | Out-Null
Invoke-Checked $Py @("-m", "brain_imager_phase3", "--config", $Cfg, "init")
```

`init` verifies and extracts the existing approved Phase 2 archive. There is no
new mapping, surrogate caption set or decoder rerun.

**Optional input reuse, before fetching:** provide the full path of the old
project's **workspace** directory, not the project directory. Press Enter to
skip reuse and fetch the pinned public inputs instead. Copy only the listed
inputs; keep old `pilot` plans/annotations/outputs in their original workspace.

```powershell
$OldWork = Read-Host "Existing verified workspace directory (Enter to skip reuse)"
if ($OldWork.Trim()) {
    if (!(Test-Path -LiteralPath $OldWork -PathType Container)) {
        throw "Old workspace directory does not exist."
    }
    foreach ($Name in @("captions", "downloads", "crops")) {
        $Source = Join-Path $OldWork $Name
        if (Test-Path -LiteralPath $Source -PathType Container) {
            Copy-Item -LiteralPath $Source -Destination $Work -Recurse
        }
    }
    $OldDb = Join-Path $OldWork "corpus.sqlite3"
    $OldSeal = Join-Path $OldWork "corpus_manifest.json"
    if ((Test-Path -LiteralPath $OldDb) -and (Test-Path -LiteralPath $OldSeal)) {
        Copy-Item -LiteralPath $OldDb -Destination $Work
        Copy-Item -LiteralPath $OldSeal -Destination $Work
    }
}
```

The copies are verified below. Copying alone is not validation. Crop directories
must include their per-image `.json` receipts; unrelated image files are not
accepted as official crops. A copied index is reused only with its manifest,
correct hashes and complete eligible identities.

```powershell
Invoke-Checked $Py @("-m", "brain_imager_phase3", "--config", $Cfg, "fetch", "--what", "captions")
Invoke-Checked $Py @("-m", "brain_imager_phase3", "--config", $Cfg, "fetch", "--what", "coco")
Invoke-Checked $Py @("-m", "brain_imager_phase3", "--config", $Cfg, "pilot")
Invoke-Checked $Py @("-m", "brain_imager_phase3", "--config", $Cfg, "fetch", "--what", "crops")
Invoke-Checked $Py @("-m", "brain_imager_phase3", "--config", $Cfg, "index")
$Validation = & $Py -m brain_imager_phase3 --config $Cfg validate --deep
if ($LASTEXITCODE -ne 0) { throw "Deep validation failed; do not proceed." }
$Validation | Set-Content -LiteralPath "$Work\deep_validation.json" -Encoding UTF8
$Validation
```

Without reusable inputs this downloads approximately 253 MB of COCO annotation
data, small cached-caption files and 20 official crops. It does not download
the full COCO image collection or NSD fMRI volumes. Data access is subject to
the original sources' terms and your completed NSD agreement.

Expected counts are 982 samples, 2,946 decoded-caption rows, 611,349 corpus
captions, 122,204 corpus images, 1,083 excluded images, 611,349 deeply checked
source rows and 20 crop receipts for the default selection. Require
`fts_external_content_verified: true`. All caption text/parent associations are
checked against the pinned ZIP. A freshly built SQLite file may have a different
binary hash across SQLite versions; it receives its own seal. The source/ID/text
checks, not matching the reviewer's database hash, are the cross-platform test.

## 5. Optional reproduction of the offline chunk diagnostic

This is the same small donor-retrieval diagnostic included in the review, not a
new RAG-generation phase. It needs no human truth labels and makes zero model
calls. It does not measure brain-caption factuality.

```powershell
$Audit = Join-Path $Work "retrieval_audit"
if (Test-Path $Audit) { throw "Audit output exists; choose a new empty output directory." }
Invoke-Checked $Py @("-m", "brain_imager_phase3", "--config", $Cfg,
    "retrieval-audit", "--candidate-images", "10000", "--queries", "100",
    "--seed", "20261028", "--output", $Audit)
Get-Content -LiteralPath "$Audit\audit_report.json" -TotalCount 35
```

Outputs are `audit_report.json`, `rankings.jsonl` and `queries.jsonl` in `$Audit`.
Temporary indexes are removed. Production `corpus.sqlite3` is not changed.
The report contains seeds, selected/query IDs, code/source hashes, tokenizer,
runtime and results. It must state `api_calls: 0` and identical metadata-only
rankings/scores. Expect the published accuracy values with the same corpus,
seed and SQLite behavior; record and investigate any discrepancy. Timing and
binary index hashes are not expected to match across machines.

The release's review evidence lives in `review\validation`; your laptop logs
are in `workspace\review_checks` and `$Work`. Do not mistake the bundled Linux
evidence for your own newly executed Windows results.

## 6. Common failures and stopping point

| Symptom | Action |
|---|---|
| `git` or `py` is not recognized | Install the missing program and reopen PowerShell; verify Python 3.12 is 64 bit. |
| `git apply --check` fails | Verify exact base, clean checkout and patch path. Use the fresh-clone route; do not force a conflicting patch. |
| Release checksum reports `CHANGED` or `MISSING` | Check incomplete patch application and LF conversion. Restore from a clean base plus patch; preserve your own edited files separately. Do not replace the expected checksum with your changed file's hash. |
| Package install fails | Check interpreter version, network/proxy and the first failed pinned dependency. Keep the pinned versions; do not silently upgrade to make installation appear successful. |
| `No module named brain_imager_phase3` | Use `$Py`, confirm the current directory is `$Project`, and rerun the editable-install command. |
| `no such module: fts5` | Use official 64-bit CPython with FTS5; do not fall back to a different retrieval algorithm. |
| Missing captions/COCO ZIP | Run the corresponding `fetch` command after `init`, or copy the exact verified file. The deep check needs the source ZIP even when the index exists. |
| Crop has no receipt or wrong provenance | Preserve the suspect file separately and acquire the official crop through `fetch --what crops`; never relabel it or manufacture a receipt. |
| Database/source hash or mapping mismatch | Stop. Keep the old file and report the exact error. Rebuild only in a new workspace from the approved source if the cause is understood. |
| Memory pressure during `validate --deep` | Close other applications or use a machine with more RAM; report the limitation rather than treating shallow validation as equivalent. |
| Old plan says code/config changed | Expected after this patch. Preserve the old experiment record; any future run requires a newly reviewed and frozen plan in a separate workspace. |
| Retrieval audit output directory already exists | Choose a new empty output directory so the previous result remains inspectable. |

Stop after these checks and review the patch, report and actual laptop logs.
Human baseline labels, verified minimal repairs and later output judgments are
still needed for the central study. This update does not supply them or infer
results. `WINDOWS_GUIDE.md` retains the earlier full pilot workflow for later
use; its generation instructions are **not** part of this review's execution.

No new dependencies were introduced. Review checks have no model/API charges.
Existing model prices and API availability must be rechecked before any later,
separately approved generation run; ChatGPT access is not API billing access.
