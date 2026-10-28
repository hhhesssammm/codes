"""Offline retrieval comparison uses synthetic donor captions only in tests."""
import json
import sqlite3
import zipfile
import pytest
from brain_imager_phase3.common import AuditError
from brain_imager_phase3.retrieval import validate_against_annotation_zip
from brain_imager_phase3.retrieval_audit import MODES, donor_split, make_units, normalized, rank_units
from brain_imager_phase3.tokenization import Tokenizer

@pytest.fixture
def donors():
    return [{'caption_id':i*10+j, 'image_id':i, 'text':t} for i, captions in [
        (1,['A red cat beside a window.', 'The small cat watches the street.', 'A feline waits by the glass.']),
        (2,['A blue bird near a tree.', 'A bird sits on a branch.', 'An animal rests in the tree.']),
        (3,['A cyclist beside a brick house.', 'A person rides a bicycle.', 'A bike moves along the road.'])] for j,t in enumerate(captions)]

def test_holdout_removes_query_ids_and_duplicate_text(donors):
    kept, queries, dropped, ids, texts = donor_split(donors+[{**donors[0], 'caption_id':999, 'image_id':4}], 3, 2026)
    assert queries
    assert all(d['caption_id'] not in ids and normalized(d['text']) not in texts for d in kept)
    assert donor_split(donors, 2, 2026) == donor_split(donors, 2, 2026)

@pytest.mark.parametrize('mode', MODES)
def test_chunks_never_cross_image_and_spans_reconstruct(donors, mode):
    original={d['caption_id']:d for d in donors}
    for u in make_units(donors,mode):
        assert {original[c]['image_id'] for c in u['source_caption_ids']} == {u['image_id']}
        spans=[original[s['caption_id']]['text'][s['start']:s['end']] for s in u['source_spans']]
        assert ('\n'.join(spans) if mode=='image_bundle' else spans[0]) == u['text']

def test_unindexed_metadata_changes_neither_scores_nor_rankings(donors, tmp_path):
    kept, queries, _, _, _ = donor_split(donors,2,2026)
    tok=Tokenizer(cache_dir=tmp_path/'tokens');results=[]
    for mode in ('whole_caption','whole_caption_metadata'):
        _, rows=rank_units(make_units(kept,mode),queries,mode,tok,tmp_path/(mode+'.db'))
        results.append([{k:v for k,v in r.items() if k!='representation'} for r in rows])
    assert results[0]==results[1]

@pytest.mark.parametrize('corrupt', ['parent', 'text'])
def test_deep_source_audit_detects_resealed_wrong_caption_mapping(tmp_path, corrupt):
    source=tmp_path/'synthetic.zip'
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('annotations/captions_train2017.json',json.dumps({'annotations':[{'id':1,'image_id':10,'caption':'A cat.'}, {'id':2,'image_id':20,'caption':'A dog.'}]}))
        z.writestr('annotations/captions_val2017.json',json.dumps({'annotations':[]}))
    with sqlite3.connect(':memory:') as con:
        con.execute('CREATE TABLE documents(caption_id INTEGER,image_id INTEGER,text TEXT)')
        con.execute('INSERT INTO documents VALUES (1,10,?)',('A cat.',))
        con.execute('INSERT INTO documents VALUES (2,20,?)',('A dog.',))
        validate_against_annotation_zip(con,source,{1,2})
        con.execute('UPDATE documents SET image_id=30-image_id' if corrupt=='parent' else "UPDATE documents SET text='A dog.' WHERE caption_id=1")
        with pytest.raises(AuditError,match='text/parent'):
            validate_against_annotation_zip(con,source,{1,2})
