"""Regression cases discovered in the repository review; synthetic data only."""
import copy
import sqlite3
from types import SimpleNamespace
import pytest
from brain_imager_phase3 import annotations
from brain_imager_phase3.common import AuditError, digest, save_json, save_jsonl, sha_bytes
from brain_imager_phase3.retrieval import Retriever


def test_crop_receipt_cannot_swap_stimulus_identity(tmp_path, monkeypatch):
    cfg = SimpleNamespace(study=tmp_path/'pilot', work=tmp_path, phase2=tmp_path/'phase2')
    (tmp_path/'crops').mkdir()
    for name, data in [('one.png', b'synthetic-one'), ('two.png', b'synthetic-two')]:
        (tmp_path/'crops'/name).write_bytes(data)
    samples = [{'coco_image_id': 1, 'nsd_id_zero_based': 10, 'official_png_name': 'one.png', 'official_png_url': 'https://example.invalid/one.png'},
               {'coco_image_id': 2, 'nsd_id_zero_based': 20, 'official_png_name': 'two.png', 'official_png_url': 'https://example.invalid/two.png'}]
    save_jsonl(cfg.phase2/'results/sample_manifest.jsonl', samples)
    save_json(cfg.phase2/'results/crop_checks.json', {'checks': []})
    # Both byte hashes are correct, but the first image is assigned the second crop.
    save_json(cfg.study/'crop_receipts.json', [
        {'coco_image_id': 1, 'nsd_id_zero_based': 20, 'filename': 'two.png', 'url': 'https://example.invalid/two.png', 'sha256': sha_bytes(b'synthetic-two')},
        {'coco_image_id': 2, 'nsd_id_zero_based': 10, 'filename': 'one.png', 'url': 'https://example.invalid/one.png', 'sha256': sha_bytes(b'synthetic-one')}])
    monkeypatch.setattr(annotations, 'load_selection', lambda c: {'coco_image_ids': [1, 2]})
    monkeypatch.setattr(annotations, 'validate_phase2', lambda c: {})
    with pytest.raises(AuditError, match='identity|provenance'):
        annotations.crop_registry(cfg)


def test_duplicate_candidate_window_does_not_hide_distinct_donors(tmp_path):
    db=tmp_path/'duplicates.sqlite3'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE documents(caption_id INTEGER PRIMARY KEY, image_id INTEGER, text TEXT)')
        rows=[(i, i, 'cat') for i in range(1, 402)] + [(402, 402, 'cat beside a window'), (403, 403, 'cat on a wall')]
        c.executemany('INSERT INTO documents VALUES (?,?,?)', rows)
        c.execute("CREATE VIRTUAL TABLE fts USING fts5(text,content='documents',content_rowid='caption_id',tokenize='porter unicode61')")
        c.execute("INSERT INTO fts(fts) VALUES ('rebuild')")
    r=Retriever(db, set(range(1,404)), set())
    try:
        docs=r.search('cat', 3)
        assert len(docs)==3
    finally:
        r.close()


@pytest.mark.parametrize('status', ['omitted', 'corrected'])
def test_persistent_error_cannot_be_scored_as_removed(pre_example, status):
    row,crop,pre=pre_example
    task={'blind_id':'synthetic', 'caption':row['caption'], 'output_sha256':digest(row['caption']),
          'crop_filename':crop['filename'], 'crop_sha256':crop['sha256']}
    review=dict(task, annotator_id='SYNTHETIC', review_complete=True, claims_complete=True, caption_usable=True,
        transitions=[{'baseline_claim_id':'c1','status':status,'evidence':'SYNTHETIC'},
                     {'baseline_claim_id':'c2','status':'retained','evidence':'SYNTHETIC'}],
        output_claims=[{'claim_id':'o1','text':'red cat','label':'contradicted','kind':'attribute','origin':'baseline','baseline_claim_id':'c1','evidence':'SYNTHETIC'},
                       {'claim_id':'o2','text':'cat','label':'supported','kind':'object','origin':'baseline','baseline_claim_id':'c2','evidence':'SYNTHETIC'}])
    if status=='corrected':
        review['output_claims'].append({'claim_id':'o3','text':'blue cat','label':'supported','kind':'attribute','origin':'correction','baseline_claim_id':'c1','evidence':'SYNTHETIC'})
    with pytest.raises(AuditError, match='persist|inventory|contradict'):
        annotations.validate_review(review, task, pre)

def test_frozen_diagnostic_flag_cannot_disable_a_focal_repair(pre_example):
    row,crop,pre=pre_example
    pre['diagnostic_eligible']=False
    with pytest.raises(AuditError,match='eligibility'):
        annotations.validate_pre_record(pre,row,crop)
