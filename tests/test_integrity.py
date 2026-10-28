import copy
from pathlib import Path
import pytest
from brain_imager_phase3.common import AuditError, strict_loads, save_json, save_jsonl, load_jsonl, unique
from brain_imager_phase3.configuration import load_config
from brain_imager_phase3.annotations import validate_pre_record
from brain_imager_phase3.assets import initialize, PHASE2_ZIP_SHA

def test_duplicate_json_keys_fail():
    with pytest.raises(AuditError): strict_loads('{"a":1,"a":2}')

@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_fail(value):
    with pytest.raises(AuditError): strict_loads('{"n":'+value+'}')

def test_duplicate_row_keys_fail():
    with pytest.raises(AuditError): unique([{"id": "a"}, {"id": "a"}], "id")

def test_windows_friendly_spaces_and_unicode_paths(tmp_path):
    p = tmp_path / "folder with spaces" / "داده.jsonl"
    save_jsonl(p, [{"caption": "café and birds"}])
    assert load_jsonl(p)[0]["caption"] == "café and birds"

def test_minimal_query_edit_preserves_nonfocal_words(pre_example):
    row, crop, ann = pre_example
    repaired = validate_pre_record(ann, row, crop)
    assert repaired == "A blue cat sits."
    assert row["caption"] == "A red cat sits."

@pytest.mark.parametrize("mutation", ["wrong_crop", "wrong_caption", "unverified", "unsupported_focal", "unrelated_edit", "delete_only"])
def test_invalid_human_repairs_block(pre_example, mutation):
    row, crop, ann = pre_example
    if mutation == "wrong_crop": ann["crop_sha256"] = "wrong"
    elif mutation == "wrong_caption": ann["caption"] = "changed"
    elif mutation == "unverified": ann["repair_verified_against_crop"] = False
    elif mutation == "unsupported_focal": ann["claims"][0]["label"] = "unverifiable"
    elif mutation == "unrelated_edit": ann["query_edit"].update(start=10, end=14)
    else: ann["query_edit"]["replacement"] = ""
    with pytest.raises(AuditError): validate_pre_record(ann, row, crop)

def test_no_error_requires_no_repair(pre_example):
    row, crop, ann = pre_example
    ann["claims"][0]["label"] = "supported"; ann["focal_claim_id"] = None; ann["query_edit"] = None
    assert validate_pre_record(ann, row, crop) == row["caption"]

def test_approved_bundle_is_present_and_valid(tmp_path):
    import json
    project = Path(__file__).resolve().parents[1]
    raw = json.loads((project / "config/pilot.json").read_text())
    raw["project_root"] = str(project); raw["workspace"] = str(tmp_path / "workspace with spaces")
    cp = tmp_path / "config.json"; save_json(cp, raw)
    result = initialize(load_config(cp))
    assert result["caption_rows"] == 2946 and result["excluded_images"] == 1083

def test_modified_phase2_zip_is_rejected(tmp_path):
    import json
    project = Path(__file__).resolve().parents[1]
    raw = json.loads((project / "config/pilot.json").read_text()); raw["project_root"] = str(tmp_path)
    raw["phase2_zip"] = "bad.zip"; (tmp_path / "bad.zip").write_bytes(b"not the approved source")
    cp = tmp_path / "config.json"; save_json(cp, raw)
    with pytest.raises(AuditError, match="hash differs"): initialize(load_config(cp))
