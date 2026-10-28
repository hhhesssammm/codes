"""Read and verify the approved Phase 2 release; never reconstruct identities by guesswork."""
from __future__ import annotations
import collections
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile
import httpx
from PIL import Image
from .common import AuditError, load_json, load_jsonl, require, save_json, sha_file, sha_bytes, unique, utc_now
from .configuration import Config

PHASE2_ZIP_SHA = "f03a3b653c94dbda169996f48f5dfd001e24c1398457e3eed4943a817df12c25"
PINNED = {
    "caption_verified_sources.json": "6f280f8df3de3299a47b342d1dfccb7d645cdaad335eedb62b6f60990c9e88e3",
    "frozen_assets.json": "0ea95f51b9e9e7ae16c3fee5fd09a7dda98d3d1c07b162a737f46e2ef0b3eef8",
    "results/alignment_manifest.jsonl": "7cc41361c032146d42a65e12ed8623edf8e0ce282af18bb7fb060daf491f93c5",
    "results/sample_manifest.jsonl": "915020aaa374bf526c672982daf25d6a64a79f2249d411a9863c871e77ce4677",
    "results/eligible_coco_caption_ids.txt": "aa2f82d55f2d963311f3b3ce56ab1cadef2a9425bed0098081817b819428d1b3",
    "results/eligible_coco_image_ids.txt": "7c564113e7818fa85eab68d074ba5099fe272a655e3750c4d396d31706faee16",
    "results/retrieval_exclusions.jsonl": "1db7b221588285652c426c1acca480aa2c467110fc4713d78a7eba94513202a2",
    "results/target_similarity_groups.json": "16a5b124ab625aca42efe6b49f88dbc509e781996593f72c45265f9d03fa66e6",
    "results/crop_checks.json": "b9e25e2da28f9eff37017f3a5d517ed59d7a4d3eedf3ef4b9ac59cf2fed11aef",
}

def initialize(cfg: Config) -> dict:
    archive = cfg.root / cfg.raw["phase2_zip"]
    require(archive.is_file(), f"Missing approved Phase 2 ZIP: {archive}. Obtain the saved audit package; no replacement dataset is generated.")
    require(sha_file(archive) == PHASE2_ZIP_SHA, "Phase 2 archive hash differs from the approved release")
    cfg.phase2.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            p = PurePosixPath(info.filename)
            require(not p.is_absolute() and ".." not in p.parts and "\\" not in info.filename,
                    "Unsafe ZIP path")
        checks = z.read("CHECKSUMS.sha256").decode().splitlines()
        for line in checks:
            expected, name = line.split("  ", 1)
            require(sha_bytes(z.read(name)) == expected, f"Phase 2 member hash mismatch: {name}")
        # Extraction is safe only after pinned archive and member integrity checks.
        z.extractall(cfg.phase2)
    return validate_phase2(cfg)

def read_ids(path: Path) -> set[int]:
    values = [int(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]
    require(len(values) == len(set(values)), f"Duplicate ID in {path.name}")
    return set(values)

def validate_phase2(cfg: Config) -> dict:
    for name, expected in PINNED.items():
        require(sha_file(cfg.phase2 / name) == expected, f"Pinned Phase 2 file changed: {name}")
    samples = load_jsonl(cfg.phase2 / "results/sample_manifest.jsonl")
    captions = load_jsonl(cfg.phase2 / "results/alignment_manifest.jsonl")
    by_sample = unique(samples, "caption_key")
    require(len(samples) == 982 and len(captions) == 2946, "Phase 2 record count mismatch")
    unique(captions, "manifest_row_id")
    for key in ["sample_key", "nsd_id_zero_based", "coco_image_id"]:
        require(len({s[key] for s in samples}) == 982, f"Duplicate stimulus {key}")
    for c in captions:
        s = by_sample.get(c["caption_key"])
        require(s is not None, "Caption refers to absent sample")
        require(all(c[k] == s[k] for k in ["sample_key", "nsd_id_zero_based", "coco_image_id", "shard", "shard_record_index"]), "Broken caption/sample join")
        require(c["validation_status"] == "PASS_RELEASED_BENCHMARK_ALIGNMENT", "Unvalidated caption row")
    eligible = read_ids(cfg.phase2 / "results/eligible_coco_image_ids.txt")
    eligible_caps = read_ids(cfg.phase2 / "results/eligible_coco_caption_ids.txt")
    ex = load_jsonl(cfg.phase2 / "results/retrieval_exclusions.jsonl")
    excluded = set(unique(ex, "coco_image_id"))
    targets = {s["coco_image_id"] for s in samples}
    require(len(eligible) == 122204 and len(eligible_caps) == 611349 and len(excluded) == 1083, "Corpus identity counts changed")
    require(not eligible & excluded and targets <= excluded, "Target/exclusion leakage in eligible IDs")
    return {"status": "pass", "sample_rows": 982, "caption_rows": 2946,
            "eligible_images": len(eligible), "eligible_captions": len(eligible_caps), "excluded_images": len(excluded)}

def download(url: str, dest: Path, expected_sha: str | None, expected_size: int | None = None) -> dict:
    if dest.exists():
        h = sha_file(dest)
        require(expected_sha is None or h == expected_sha, f"Existing download failed hash check: {dest}")
        require(expected_size is None or dest.stat().st_size == expected_size, f"Existing download has wrong size: {dest}")
        return {"url": url, "sha256": h, "bytes": dest.stat().st_size, "status": "verified_existing"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    h = hashlib.sha256(); count = 0
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=90) as r:
            r.raise_for_status()
            with partial.open("wb") as f:
                for b in r.iter_bytes(chunk_size=1024 * 1024):
                    f.write(b); h.update(b); count += len(b)
            etag = r.headers.get("etag")
        require(expected_sha is None or h.hexdigest() == expected_sha, f"Downloaded SHA-256 mismatch: {dest.name}")
        require(expected_size is None or count == expected_size, f"Downloaded size mismatch: {dest.name}")
        partial.replace(dest)
    except httpx.HTTPError as exc:
        raise AuditError(f"Download failed for {dest.name}: {type(exc).__name__}. The .part file is not a validated input; rerun fetch to restart.") from exc
    return {"url": url, "sha256": h.hexdigest(), "bytes": count, "etag": etag,
            "status": "downloaded_verified", "completed_utc": utc_now()}

def fetch_captions(cfg: Config) -> dict:
    validate_phase2(cfg)
    results = []
    for s in load_json(cfg.phase2 / "caption_verified_sources.json"):
        p = cfg.work / "captions" / Path(s["local_path"]).name
        results.append(download(s["url"], p, s["sha256"], s["size"]))
        b = p.read_bytes()
        require(hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest() == s["sha"], "Git blob hash mismatch")
    save_json(cfg.work / "caption_downloads.json", results)
    return validate_captions(cfg)

def validate_captions(cfg: Config) -> dict:
    validate_phase2(cfg)
    sources = {s["label"]: s for s in load_json(cfg.phase2 / "caption_verified_sources.json")}
    rows = load_jsonl(cfg.phase2 / "results/alignment_manifest.jsonl")
    for label in ["umbrae", "braincap", "mindeye2", "references"]:
        s = sources[label]; p = cfg.work / "captions" / Path(s["local_path"]).name
        require(sha_file(p) == s["sha256"], f"Caption file differs from frozen {label} source")
        d = load_json(p)
        require(list(d) == [str(i) for i in range(982)], f"{label} caption key/order mismatch")
        if label != "references":
            require(all(isinstance(v, str) and v.strip() for v in d.values()), "Empty/nontext caption")
            for r in rows:
                if r["decoder"] == label:
                    require(sha_bytes(d[r["caption_key"]].encode()) == r["caption_utf8_sha256"], "Caption row text hash mismatch")
    return {"status": "pass", "caption_rows_verified": 2946}

def decoded_rows(cfg: Config) -> list[dict]:
    validate_captions(cfg)
    sources = {s["label"]: s for s in load_json(cfg.phase2 / "caption_verified_sources.json")}
    texts = {label: load_json(cfg.work / "captions" / Path(sources[label]["local_path"]).name) for label in cfg.raw["decoders"]}
    return [dict(r, caption=texts[r["decoder"]][r["caption_key"]])
            for r in load_jsonl(cfg.phase2 / "results/alignment_manifest.jsonl") if r["decoder"] in texts]

def fetch_coco(cfg: Config) -> dict:
    validate_phase2(cfg)
    s = next(s for s in load_json(cfg.phase2 / "frozen_assets.json") if s["id"] == "coco_annotations")
    result = download(s["url"], cfg.work / "downloads" / s["filename"], s["sha256"], s["bytes"])
    save_json(cfg.work / "coco_download.json", result)
    return result

def fetch_crops(cfg: Config) -> dict:
    from .selection import load_selection
    require(cfg.raw["nsd_access_agreement_confirmed"] is True, "NSD agreement must be completed before crop use")
    selected = load_selection(cfg)
    samples = {s["coco_image_id"]: s for s in load_jsonl(cfg.phase2 / "results/sample_manifest.jsonl")}
    prior = {r["coco_image_id"]: r for r in load_json(cfg.phase2 / "results/crop_checks.json")["checks"]}
    receipts = []
    for iid in selected["coco_image_ids"]:
        s = samples[iid]; p = cfg.work / "crops" / s["official_png_name"]
        expected = prior.get(iid, {}).get("file_sha256")
        old = cfg.work / "crops" / (s["official_png_name"] + ".json")
        if old.exists():
            old_r = load_json(old)
            require(old_r["url"] == s["official_png_url"], "Crop provenance URL changed")
            expected = expected or old_r["sha256"]
        require(not p.exists() or expected is not None,
                f"Existing crop {p.name} has no trusted download receipt or Phase 2 hash. Move that unverified file aside before fetching the official image.")
        result = download(s["official_png_url"], p, expected)
        with Image.open(p) as im:
            require(im.format == "PNG" and im.size == (425, 425), "Not an official-size NSD PNG")
            im.convert("RGB").load()
        result.update(coco_image_id=iid, nsd_id_zero_based=s["nsd_id_zero_based"],
                      filename=s["official_png_name"], hash_previously_verified_in_phase2=iid in prior)
        save_json(old, result); receipts.append(result)
    save_json(cfg.study / "crop_receipts.json", receipts)
    return {"official_crops_available": len(receipts), "new_bytes_locally_frozen": sum(not r["hash_previously_verified_in_phase2"] for r in receipts)}

