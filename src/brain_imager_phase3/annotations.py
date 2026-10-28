"""Human evidence is required. Templates deliberately contain no inferred truth labels."""
from __future__ import annotations
from pathlib import Path
from .common import digest, load_json, load_jsonl, require, save_json, save_jsonl, sha_bytes, sha_file, unique
from .selection import pilot_rows, load_selection

LABELS = {"supported", "contradicted", "unverifiable"}
KINDS = {"object", "attribute", "count", "action", "relation", "scene", "other"}
TRANSITIONS = {
    "contradicted": {"persisted", "corrected", "omitted", "unverifiable"},
    "supported": {"retained", "contradicted", "omitted", "unverifiable"},
    "unverifiable": {"retained", "omitted", "unverifiable"},
}

def crop_registry(cfg):
    receipts = load_json(cfg.study / "crop_receipts.json")
    out = unique(receipts, "coco_image_id")
    require(set(out) == set(load_selection(cfg)["coco_image_ids"]), "Crop receipts do not cover the frozen pilot")
    for r in receipts:
        require(sha_file(cfg.work / "crops" / r["filename"]) == r["sha256"], "Official crop bytes changed")
    return out

def create_pre_templates(cfg, rater: str):
    require(rater and rater.replace("_", "").replace("-", "").isalnum(), "Use a simple rater ID, e.g. R1")
    path = cfg.study / "annotations" / f"pre_{rater}.jsonl"
    if path.exists():
        return {"path": str(path), "status": "existing file preserved"}
    crops = crop_registry(cfg)
    rows = []
    for r in pilot_rows(cfg):
        rows.append({"row_id": r["manifest_row_id"], "caption": r["caption"],
                     "caption_sha256": r["caption_utf8_sha256"], "crop_filename": crops[r["coco_image_id"]]["filename"],
                     "crop_sha256": crops[r["coco_image_id"]]["sha256"], "annotator_id": rater,
                     "claims_complete": False, "review_complete": False,
                     "claims": [], "focal_claim_id": None, "query_edit": None,
                     "repair_verified_against_crop": False, "diagnostic_exclusion_reason": "", "notes": ""})
    save_jsonl(path, rows)
    return {"path": str(path), "rows": len(rows), "status": "unannotated templates"}

def validate_pre_record(a, row, crop):
    require(a["row_id"] == row["manifest_row_id"], "Annotation identity mismatch")
    require(a["caption"] == row["caption"] and a["caption_sha256"] == row["caption_utf8_sha256"], "Annotation caption was changed")
    require(a["crop_sha256"] == crop["sha256"] and a["crop_filename"] == crop["filename"], "Annotation refers to another crop")
    require(a["review_complete"] is True and a["claims_complete"] is True and bool(a["annotator_id"].strip()), "Human review/claim coverage is incomplete")
    claims = unique(a["claims"], "claim_id")
    require(len(claims) > 0, "Annotate at least one atomic claim, using unverifiable when appropriate")
    for c in claims.values():
        require(c["label"] in LABELS and c["kind"] in KINDS and bool(c["text"].strip()), "Invalid claim label/kind/text")
        require(isinstance(c["start"], int) and isinstance(c["end"], int) and 0 <= c["start"] < c["end"] <= len(row["caption"]), "Claim span is outside the source caption")
        require(bool(c.get("evidence", "").strip()), "Record crop-grounded evidence or uncertainty for every claim")
    focal = a.get("focal_claim_id")
    repaired = row["caption"]
    if focal is not None:
        require(focal in claims and claims[focal]["label"] == "contradicted", "Focal error must be a visually contradicted baseline claim")
        edit = a.get("query_edit")
        require(isinstance(edit, dict), "Supply a human minimal edit for the focal error")
        start, end = edit["start"], edit["end"]
        require(isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(repaired), "Invalid repair span")
        require(start < claims[focal]["end"] and end > claims[focal]["start"], "Repair does not overlap the preselected focal claim")
        require(isinstance(edit["replacement"], str) and edit["replacement"].strip(), "Use an explicit correction, not an empty deletion")
        require(a["repair_verified_against_crop"] is True and bool(edit.get("reason", "").strip()), "Repair requires human visual verification and rationale")
        repaired = repaired[:start] + edit["replacement"] + repaired[end:]
        require(repaired != row["caption"], "Repair made no change")
    else:
        require(a.get("query_edit") is None, "A repair without a focal error is not allowed")
        if any(c["label"] == "contradicted" for c in claims.values()):
            require(bool(a.get("diagnostic_exclusion_reason", "").strip()), "Explain why contradicted claims have no usable focal repair")
    return repaired

def freeze_pre(cfg, annotation_path: Path, annotation_policy: str):
    require(annotation_policy in {"single_rater_pilot", "adjudicated_pilot"}, "State the human annotation policy explicitly")
    annotations = unique(load_jsonl(annotation_path), "row_id")
    rows = pilot_rows(cfg); crops = crop_registry(cfg)
    require(set(annotations) == {r["manifest_row_id"] for r in rows}, "Annotation IDs must exactly cover the pilot and selected decoders")
    frozen = []
    for r in rows:
        a = annotations[r["manifest_row_id"]]
        repaired = validate_pre_record(a, r, crops[r["coco_image_id"]])
        frozen.append(dict(a, repaired_query=repaired, diagnostic_eligible=a["focal_claim_id"] is not None))
    data = {"schema_version": 1, "annotation_policy": annotation_policy,
            "source_annotation_sha256": sha_file(annotation_path), "selection_sha256": load_selection(cfg)["selection_sha256"], "rows": frozen}
    data["frozen_sha256"] = digest(data)
    path = cfg.study / "frozen_pre_annotations.json"
    if path.exists():
        require(load_json(path) == data, "Input annotations are already frozen. Do not repair them after seeing outputs.")
    else:
        save_json(path, data)
    return {"frozen_file": str(path), "rows": len(frozen), "focal_error_rows": sum(r["diagnostic_eligible"] for r in frozen), "sha256": data["frozen_sha256"]}

def load_frozen_pre(cfg):
    data = load_json(cfg.study / "frozen_pre_annotations.json")
    require(data["frozen_sha256"] == digest({k: v for k, v in data.items() if k != "frozen_sha256"}), "Frozen annotation digest mismatch")
    require(data["selection_sha256"] == load_selection(cfg)["selection_sha256"], "Frozen annotations use another pilot")
    by_id = unique(data["rows"], "row_id")
    rows = pilot_rows(cfg); crops = crop_registry(cfg)
    require(set(by_id) == {r["manifest_row_id"] for r in rows}, "Frozen annotation coverage mismatch")
    for row in rows:
        a = by_id[row["manifest_row_id"]]
        require(validate_pre_record(a, row, crops[row["coco_image_id"]]) == a["repaired_query"], "Repaired query was altered")
    return data

def validate_review(a, task, pre):
    require(a["blind_id"] == task["blind_id"] and a["output_sha256"] == task["output_sha256"], "Review output identity/hash mismatch")
    require(a["caption"] == task["caption"] and a["crop_sha256"] == task["crop_sha256"] and a["crop_filename"] == task["crop_filename"], "Review stimulus/text was changed")
    require(a["review_complete"] is True and a["claims_complete"] is True and bool(a["annotator_id"].strip()), "Output review is incomplete")
    base = unique(pre["claims"], "claim_id")
    transitions = unique(a["transitions"], "baseline_claim_id")
    require(set(transitions) == set(base), "Every baseline claim needs a transition decision")
    for cid, t in transitions.items():
        require(t["status"] in TRANSITIONS[base[cid]["label"]], f"Invalid transition for {cid}")
        require(bool(t.get("evidence", "").strip()), "Transition needs evidence")
    outclaims = unique(a["output_claims"], "claim_id")
    for c in outclaims.values():
        require(c["label"] in LABELS and c["kind"] in KINDS and bool(c["text"].strip()), "Invalid output claim")
        require(c["origin"] in {"baseline", "correction", "new"}, "Label output claim origin")
        require(bool(c.get("evidence", "").strip()), "Output claim needs image evidence/uncertainty")
        if c["origin"] == "new":
            require(c.get("baseline_claim_id") is None, "New claim must not link to a baseline claim")
        else:
            require(c.get("baseline_claim_id") in base, "Baseline/correction claim must link to a valid baseline claim")
    require(isinstance(a["caption_usable"], bool), "Mark caption_usable as true or false")
    if not outclaims:
        require(a["caption_usable"] is False, "A usable caption must have at least one output claim")
    for cid, t in transitions.items():
        linked = [c for c in outclaims.values() if c.get("baseline_claim_id") == cid]
        if t["status"] == "corrected":
            require(any(c["origin"] == "correction" and c["label"] == "supported" for c in linked), "Explicit correction requires a supported replacement claim linked to the original error")
        if t["status"] == "persisted":
            require(any(c["origin"] == "baseline" and c["label"] == "contradicted" for c in linked), "Persisted error must appear in the output claim inventory")
        if t["status"] == "retained" and base[cid]["label"] == "supported":
            require(any(c["label"] == "supported" for c in linked), "Retained correct claim needs a supported output claim")
        if t["status"] == "contradicted":
            require(any(c["label"] == "contradicted" for c in linked), "Corrupted supported claim needs a contradicted output claim")
    return True
