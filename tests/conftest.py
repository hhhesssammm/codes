"""Only synthetic fixtures live here. They are not research data or results."""
import sqlite3
from pathlib import Path
import pytest

@pytest.fixture
def tiny_db(tmp_path):
    db = tmp_path / "synthetic.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE documents(caption_id INTEGER PRIMARY KEY,image_id INTEGER,text TEXT)")
        con.executemany("INSERT INTO documents VALUES (?,?,?)", [
            (1, 101, "A red cat sits beside a very large window."),
            (2, 101, "A red cat sits."),
            (3, 102, "A blue cat sits beside a very large window."),
            (4, 103, "A person rides a bicycle on a road near a brick wall."),
            (5, 104, "A green bird stands beside a tree on a very sunny morning."),
            (6, 105, "A red cat sits beside a very large window."),
        ])
        con.execute("CREATE VIRTUAL TABLE fts USING fts5(text,content='documents',content_rowid='caption_id',tokenize='porter unicode61')")
        con.execute("INSERT INTO fts(fts) VALUES ('rebuild')")
    return db

@pytest.fixture
def pre_example():
    from brain_imager_phase3.common import sha_bytes
    caption = "A red cat sits."
    row = {"manifest_row_id": "SYNTHETIC_TEST:0", "caption": caption, "caption_utf8_sha256": sha_bytes(caption.encode())}
    crop = {"filename": "synthetic.png", "sha256": "synthetic-crop-hash"}
    ann = {"row_id": row["manifest_row_id"], "caption": caption, "caption_sha256": row["caption_utf8_sha256"],
           "crop_filename": crop["filename"], "crop_sha256": crop["sha256"], "annotator_id": "SYNTHETIC_TEST_RATER",
           "claims_complete": True, "review_complete": True,
           "claims": [{"claim_id": "c1", "text": "The cat is red", "label": "contradicted", "kind": "attribute", "start": 2, "end": 5, "evidence": "SYNTHETIC TEST ONLY: assume blue"},
                      {"claim_id": "c2", "text": "There is a cat", "label": "supported", "kind": "object", "start": 6, "end": 9, "evidence": "SYNTHETIC TEST ONLY"}],
           "focal_claim_id": "c1", "query_edit": {"start": 2, "end": 5, "replacement": "blue", "reason": "SYNTHETIC TEST ONLY"},
           "repair_verified_against_crop": True, "diagnostic_exclusion_reason": "", "notes": "SYNTHETIC TEST ONLY"}
    return row, crop, ann
