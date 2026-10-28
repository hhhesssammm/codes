import copy
import json
import httpx
import pytest
from brain_imager_phase3.common import AuditError
from brain_imager_phase3.provider import OpenAIProvider, ProviderFailure, parse_response
from brain_imager_phase3.prompts import request_body
from brain_imager_phase3.execution import Ledger
from brain_imager_phase3.planning import cost_reservation

MODEL = {"model":"gpt-5.4-mini-2026-03-17","base_url":"https://api.openai.com/v1","api_key_env":"TEST_ONLY_API_KEY","reasoning_effort":"none","max_completion_tokens":256,"timeout_seconds":5,"input_usd_per_million":.75,"output_usd_per_million":4.5}

def response(caption='SYNTHETIC TEST OUTPUT'):
    return {"id":"test-response","model":MODEL['model'],"choices":[{"finish_reason":"stop","message":{"content":json.dumps({"caption":caption})}}],"usage":{"prompt_tokens":50,"completion_tokens":8}}

def test_mock_http_transport_and_schema(monkeypatch):
    monkeypatch.setenv('TEST_ONLY_API_KEY','synthetic-not-a-real-key')
    seen=[]
    def handler(req):
        seen.append(json.loads(req.content));return httpx.Response(200,json=response(),headers={'x-request-id':'test-only'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        p=OpenAIProvider(MODEL,client)
        out=p.generate(request_body(MODEL,'A red cat.','Example 1: a blue dog.'),'test-request')
    assert out['caption']=='SYNTHETIC TEST OUTPUT'
    assert seen[0]['store'] is False and seen[0]['max_completion_tokens']==256
    assert 'TEST_ONLY_API_KEY' not in json.dumps(seen)

@pytest.mark.parametrize('bad',['refusal','truncated','json','extra_field','empty'])
def test_invalid_outputs_do_not_become_source_caption(bad):
    r=response()
    if bad=='refusal':r['choices'][0]['message']['refusal']='no'
    elif bad=='truncated':r['choices'][0]['finish_reason']='length'
    elif bad=='json':r['choices'][0]['message']['content']='not json'
    elif bad=='extra_field':r['choices'][0]['message']['content']='{"caption":"x","truth":true}'
    else:r['choices'][0]['message']['content']='{"caption":""}'
    with pytest.raises(ProviderFailure):parse_response(r)

def test_http_error_does_not_echo_key(monkeypatch):
    monkeypatch.setenv('TEST_ONLY_API_KEY','synthetic-not-a-real-key')
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(401,json={'error':'synthetic-not-a-real-key'}))) as client:
        with pytest.raises(ProviderFailure) as e:OpenAIProvider(MODEL,client).generate(request_body(MODEL,'x',''),'r')
    assert e.value.raw is None and 'synthetic-not-a-real-key' not in str(e.value)

@pytest.mark.parametrize('raw', [None, [], {'choices':None}, {'choices':[None]}, {'choices':[{'message':None}]}])
def test_malformed_envelopes_fail_explicitly(raw):
    with pytest.raises(ProviderFailure):
        parse_response(raw)

def test_reservation_precedes_call_and_counts_failed_attempts(tmp_path):
    l=Ledger(tmp_path/'ledger.sqlite3','test-plan')
    limits={'max_api_attempts':2,'max_estimated_usd':.5,'max_attempts_per_job':2}
    aid=l.start('a',.3,limits,False)
    assert l.totals()['api_attempts']==1
    l.finish('a',aid,None,{'code':'timeout'},MODEL)
    with pytest.raises(AuditError,match='previous attempt'):l.start('a',.1,limits,False)
    with pytest.raises(AuditError,match='Cost reservation'):l.start('b',.3,limits,False)
    l.start('a',.1,limits,True)
    with pytest.raises(AuditError):l.start('c',.01,limits,False)
    l.close()

def test_plan_mismatch_refuses_reuse(tmp_path):
    p=tmp_path/'ledger.sqlite3';l=Ledger(p,'plan-a');l.close()
    with pytest.raises(AuditError):Ledger(p,'plan-b')

def test_payload_never_contains_oracle_metadata():
    b=request_body(MODEL,'unchanged erroneous caption','other-image example')
    user=json.loads(b['messages'][1]['content'])
    assert set(user)=={'source_caption','other_image_caption_examples'}
    assert not any(k in json.dumps(b) for k in ['nsd_id','reference_caption','focal_claim_id','repaired_query','crop_filename'])
    assert cost_reservation(b,MODEL)['reserved_usd']>0

def test_unexpected_returned_model_is_not_accepted(monkeypatch):
    monkeypatch.setenv('TEST_ONLY_API_KEY','synthetic-not-a-real-key')
    raw=response();raw['model']='different-unplanned-model'
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=raw))) as client:
        with pytest.raises(ProviderFailure,match='model'):
            OpenAIProvider(MODEL,client).generate(request_body(MODEL,'caption',''),'synthetic')
