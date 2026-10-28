import random
import pytest
from brain_imager_phase3.common import AuditError
from brain_imager_phase3.retrieval import Retriever, match_query, render_context
from brain_imager_phase3.tokenization import Tokenizer

def test_bm25_rank_and_image_text_deduplication(tiny_db):
    r = Retriever(tiny_db, {101,102,103,104,105}, {999})
    docs = r.search("red cat", 4)
    assert docs[0]["image_id"] == 101
    assert len({d["image_id"] for d in docs}) == len(docs)
    assert len({" ".join(d["text"].lower().split()) for d in docs}) == len(docs)
    assert docs == r.search("red cat", 4)
    r.close()

def test_excluded_target_retrieval_fails_closed(tiny_db):
    r = Retriever(tiny_db, {101,102,103,104,105}, {101})
    with pytest.raises(AuditError, match="leakage"): r.search("red cat", 1)
    r.close()

def test_query_syntax_is_not_sql_or_fts_code(tiny_db):
    r = Retriever(tiny_db, {101,102,103,104,105}, set())
    assert '"' in match_query('red " OR *; DROP TABLE documents; --')
    r.search('red " OR *; DROP TABLE documents; --', 2)
    assert r.conn.execute('select count(*) from documents').fetchone()[0] == 6
    assert r.search('the a is', 3) == []
    r.close()

def test_random_context_is_reproducible_and_eligible(tiny_db, tmp_path):
    t = Tokenizer(cache_dir=tmp_path / "tokens")
    r = Retriever(tiny_db, {101,102,103,104,105}, {999})
    a = r.random_context(2, random.Random(12), 10, t)
    b = r.random_context(2, random.Random(12), 10, t)
    assert a == b and len({d["image_id"] for d in a}) == 2
    assert t.count(render_context(a)[0]) >= 10
    r.close()

def test_unicode_clipping_never_introduces_replacement_characters(tmp_path):
    t = Tokenizer(cache_dir=tmp_path / "token cache")
    text = "A café with 🦜 birds and ماشین."
    for limit in range(1, t.count(text)+1):
        clipped = t.clip(text, limit)
        assert "\ufffd" not in clipped and text.startswith(clipped) and t.count(clipped) <= limit
    a,b = t.matched([text, 'A very long image caption about a bicycle and a forest.'], 9)
    assert t.count(a) == t.count(b)

def test_retrieval_metadata_does_not_enter_generator_context(tiny_db):
    r=Retriever(tiny_db,{101,102,103,104,105},set())
    try:
        docs=r.search('red cat',2);text=render_context(docs)[0]
        assert all(d['retrieval_unit']=='whole_caption' and d['source_caption_ids']==[d['caption_id']] for d in docs)
        assert 'coco:caption:' not in text and 'sha256' not in text
        assert r.last_search_stats['returned']==len(docs)
    finally:r.close()

def test_partial_displayed_caption_is_explicitly_logged(tmp_path):
    from brain_imager_phase3.planning import context_record
    tok=Tokenizer(cache_dir=tmp_path/'tokens')
    docs=[{'caption_id':1,'image_id':10,'text':'A cat beside a window.'}]
    result=context_record(docs,'Example 1: A cat',tok)
    assert result['partial_caption_count']==1 and result['displayed_documents'][0]['fully_displayed'] is False
