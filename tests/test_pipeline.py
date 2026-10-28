"""Synthetic end-to-end pipeline test. No NSD truth labels and no paid requests."""
import copy
import json
from pathlib import Path
import pytest
from brain_imager_phase3.common import save_json, save_jsonl, load_json, load_jsonl, AuditError
from brain_imager_phase3.configuration import Config
from brain_imager_phase3.annotations import validate_pre_record
from brain_imager_phase3 import planning, execution, evaluation

@pytest.fixture
def synthetic_plan(tmp_path, tiny_db, pre_example, monkeypatch):
    import shutil
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root/'config/pilot.json').read_text())
    raw['pilot_size']=1; raw['retrieval']['top_k']=1
    cfg=Config(raw,tmp_path,tmp_path/'workspace',tmp_path/'phase2',tmp_path/'config.json')
    cfg.work.mkdir();shutil.copy2(tiny_db,cfg.work/'corpus.sqlite3')
    row,crop,ann=pre_example
    row.update(subject='subj01',decoder='umbrae',decoder_variant={'label':'SYNTHETIC TEST ONLY'},
               coco_image_id=1000,nsd_id_zero_based=999,sample_key='SYNTHETIC',caption_file_sha256='SYNTHETIC')
    ann['repaired_query']=validate_pre_record(ann,row,crop);ann['diagnostic_eligible']=True
    pre={'rows':[ann],'frozen_sha256':'SYNTHETIC_PRE'}
    save_json(cfg.phase2/'results/target_similarity_groups.json',{'components':[[1000]]})
    save_jsonl(cfg.phase2/'results/retrieval_exclusions.jsonl',[{'coco_image_id':1000}])
    monkeypatch.setattr(planning,'load_frozen_pre',lambda c:pre)
    monkeypatch.setattr(planning,'validate_index',lambda c:{'database_sha256':'SYNTHETIC_DB'})
    monkeypatch.setattr(planning,'read_ids',lambda p:{101,102,103,104,105})
    monkeypatch.setattr(planning,'pilot_rows',lambda c:[row])
    monkeypatch.setattr(planning,'load_selection',lambda c:{'selection_sha256':'SYNTHETIC_SELECTION'})
    planning.create_plan(cfg)
    plan=load_json(cfg.study/'plan.json')
    monkeypatch.setattr(execution,'load_plan',lambda c:plan)
    monkeypatch.setattr(evaluation,'load_plan',lambda c:plan)
    monkeypatch.setattr(evaluation,'load_frozen_pre',lambda c:pre)
    return cfg,plan,pre

def test_factorial_query_only_control(synthetic_plan):
    cfg,plan,pre=synthetic_plan
    jobs={j['condition']:j for j in plan['jobs']}
    assert set(jobs)==set(planning.CONDITIONS)
    def user(name):return json.loads(jobs[name]['request_body']['messages'][1]['content'])
    original=user('rag_original');query_only=user('rag_query_repaired')
    assert original['source_caption']==query_only['source_caption']=='A red cat sits.'
    assert original['other_image_caption_examples']!=query_only['other_image_caption_examples']
    assert user('rag_caption_repaired')['source_caption']=='A blue cat sits.'
    assert user('rag_caption_repaired')['other_image_caption_examples']==original['other_image_caption_examples']
    assert user('rag_both_repaired')['other_image_caption_examples']==query_only['other_image_caption_examples']
    assert user('rewrite_only')['other_image_caption_examples']==''
    assert all(d['image_id']!=1000 for ctx in plan['contexts'] for d in ctx['retrieved_documents'])
    assert plan['retrieval_diagnostics'][0]['matched_context_lengths'] is True

class SyntheticProvider:
    calls=0
    def __init__(self, config):self.config=config
    def close(self):pass
    def generate(self,body,request_id):
        type(self).calls+=1
        source=json.loads(body['messages'][1]['content'])['source_caption']
        return {'caption':source.replace('red','blue'),'response_id':'SYNTHETIC_TEST_ONLY',
                'returned_model':'SYNTHETIC_TEST_ONLY','prompt_tokens':50,'completion_tokens':10,
                'usage':{'prompt_tokens':50,'completion_tokens':10},'raw_response':{'synthetic_test_only':True}}

def test_preview_never_instantiates_a_provider(synthetic_plan):
    cfg,plan,pre=synthetic_plan
    def forbidden(_):raise AssertionError('No API client in preview mode')
    result=execution.execute_plan(cfg,provider_factory=forbidden)
    assert result['api_calls_made']==0 and not (cfg.study/'outputs.jsonl').exists()

def test_resume_cache_and_evaluation_end_to_end(synthetic_plan):
    cfg,plan,pre=synthetic_plan;SyntheticProvider.calls=0
    execution.execute_plan(cfg,True,max_calls=1,provider_factory=SyntheticProvider)
    assert SyntheticProvider.calls==1
    with pytest.raises(AuditError,match='incomplete'):evaluation.make_review(cfg,'R1')
    execution.execute_plan(cfg,True,provider_factory=SyntheticProvider)
    assert SyntheticProvider.calls==plan['unique_api_requests']
    execution.execute_plan(cfg,True,provider_factory=SyntheticProvider)
    assert SyntheticProvider.calls==plan['unique_api_requests']
    result=evaluation.make_review(cfg,'R1')
    path=Path(result['review_file']);reviews=load_jsonl(path)
    for a in reviews:
        red='red' in a['caption'];a.update(review_complete=True,claims_complete=True)
        a['transitions']=[{'baseline_claim_id':'c1','status':'persisted' if red else 'corrected','evidence':'SYNTHETIC TEST ONLY'},
                          {'baseline_claim_id':'c2','status':'retained','evidence':'SYNTHETIC TEST ONLY'}]
        a['output_claims']=[{'claim_id':'o1','text':'cat color','label':'contradicted' if red else 'supported','kind':'attribute',
                            'origin':'baseline' if red else 'correction','baseline_claim_id':'c1','evidence':'SYNTHETIC TEST ONLY'},
                           {'claim_id':'o2','text':'cat exists','label':'supported','kind':'object','origin':'baseline','baseline_claim_id':'c2','evidence':'SYNTHETIC TEST ONLY'}]
    save_jsonl(path,reviews)
    evaluated=evaluation.evaluate(cfg,path,100)
    assert evaluated['reviewed_outputs']==7
    summary=load_json(cfg.study/'evaluation/pilot_summary.json')
    assert all(r['ci95'] is None for r in summary['paired_contrasts'])
    assert 'pilot' in summary['scope'].lower()
    receipt=load_json(cfg.study/'execution_receipt.json')
    assert receipt['api_attempts']==plan['unique_api_requests']
    decoded_job=next(j['job_id'] for j in plan['jobs'] if j['condition']=='decoded')
    key=next(k for k in load_jsonl(cfg.study/'private/review_key.jsonl') if decoded_job in k['job_ids'])
    changed=next(a for a in reviews if a['blind_id']==key['blind_id'])
    changed['transitions'][0]['status']='omitted'
    changed['output_claims']=[c for c in changed['output_claims'] if c['claim_id']!='o1']
    save_jsonl(path,reviews)
    with pytest.raises(AuditError,match='Unchanged-baseline'):evaluation.evaluate(cfg,path,100)
    assert load_json(cfg.study/'evaluation/pilot_summary.json')['status'].startswith('blocked')

def test_missing_reviews_do_not_silently_drop_rows(synthetic_plan):
    cfg,plan,pre=synthetic_plan
    execution.execute_plan(cfg,True,provider_factory=SyntheticProvider)
    result=evaluation.make_review(cfg,'R1');p=Path(result['review_file'])
    save_jsonl(p,load_jsonl(p)[:-1])
    with pytest.raises(AuditError,match='every task'):evaluation.validated_reviews(cfg,p)
