import copy
import pytest
from brain_imager_phase3.evaluation import claim_metrics, paired_contrast
from brain_imager_phase3.annotations import validate_review
from brain_imager_phase3.common import AuditError

def test_omission_is_not_correction_and_unknown_is_not_false(pre_example):
    row,crop,pre=pre_example
    review={'caption':'A cat.', 'caption_usable':True,
            'transitions':[{'baseline_claim_id':'c1','status':'omitted'},{'baseline_claim_id':'c2','status':'retained'}],
            'output_claims':[{'origin':'baseline','label':'supported'}, {'origin':'new','label':'unverifiable'}]}
    m=claim_metrics(review,pre)
    assert m['explicit_correction_rate']==0 and m['false_claim_omission_rate']==1
    assert m['new_false_claims']==0 and m['new_unverifiable_claims']==1

def test_uncertain_transition_produces_bounds_not_false_certainty(pre_example):
    pre=pre_example[2]
    review={'caption':'SYNTHETIC', 'caption_usable':True,'transitions':[{'baseline_claim_id':'c1','status':'unverifiable'},{'baseline_claim_id':'c2','status':'retained'}], 'output_claims':[]}
    m=claim_metrics(review,pre)
    assert m['focal_error_persistence'] is None and m['focal_persistence_lower']==0 and m['focal_persistence_upper']==1

def test_false_attempted_correction_counts_as_new_error(pre_example):
    pre=pre_example[2]
    review={'caption':'SYNTHETIC','caption_usable':True,'transitions':[{'baseline_claim_id':'c1','status':'omitted'},{'baseline_claim_id':'c2','status':'retained'}],
            'output_claims':[{'origin':'correction','label':'contradicted'}]}
    assert claim_metrics(review,pre)['new_false_claims']==1

def test_cluster_bootstrap_does_not_count_repeats_as_stimuli():
    rows=[]
    for stimulus in range(6):
        for rep in range(3):
            for cond,val in [('a',1.),('b',0.)]:
                rows.append({'row_id':str(stimulus),'repeat':rep,'condition':cond,'cluster_id':stimulus if stimulus<5 else 4,'metric':val})
    result=paired_contrast(rows,'a','b','metric',42,100)
    assert result['paired_stimulus_rows']==6 and result['paired_replicates']==18
    assert result['independent_similarity_clusters']==5 and result['mean_difference']==-1
    assert result['ci95']==[-1,-1]

def test_no_eligible_errors_returns_null_not_zero_effect():
    result=paired_contrast([{'row_id':'a','repeat':0,'condition':'a','cluster_id':1,'m':None}], 'a','b','m',1,100)
    assert result['mean_difference'] is None and result['paired_stimulus_rows']==0
