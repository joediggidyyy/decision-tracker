import pytest
from decision_tracker.errors import Fault
from conftest import change

def create(ledger):
    s,p,u=ledger
    change(s,p,u,[{"op":"decision.create","data":{"title":"Storage","question":"Which storage?"}}])
    return s,p,u

def test_close_lock_amend_preserves_baseline(ledger):
    s,p,u=create(ledger)
    change(s,p,u,[{"op":"decision.close","key":"D000001","data":{"answer":"SQLite","rationale":"Portable"}}],1,{"D000001":1},authority_refs=["operator:scope"])
    change(s,p,u,[{"op":"decision.lock","key":"D000001","data":{"baseline":"v1"}}],2,{"D000001":2},authority_refs=["operator:baseline"])
    with pytest.raises(Fault,match="protected"):
        change(s,p,u,[{"op":"decision.edit","key":"D000001","data":{"title":"Overwrite"}}],3,{"D000001":3})
    change(s,p,u,[{"op":"decision.amend","key":"D000001","data":{"title":"Amendment","question":"Change storage?","impact":"Compatibility","baseline_disposition":"continue"}}],3,{"D000001":3},authority_refs=["operator:review"])
    before=s.detail("alpha",u,p,"D000001",3)["data"]
    after=s.detail("alpha",u,p,"D000001")["data"]
    assert before["answer"]==after["answer"]=="SQLite"
    assert after["locked"] and after["revision"]==4
    assert s.detail("alpha",u,p,"D000002")["data"]["work_tag"]=="under-investigation"

def test_defer_challenge_and_independent_evidence(ledger):
    s,p,u=create(ledger)
    change(s,p,u,[{"op":"decision.defer","key":"D000001","data":{"resume_trigger":"Owner response"}},
                   {"op":"decision.challenge","key":"D000001"},
                   {"op":"decision.edit","key":"D000001","data":{"evidence_state":{"verification":{"status":"reviewed"}}}}],1,{"D000001":1})
    item=s.detail("alpha",u,p,"D000001")["data"]
    assert item["status"]=="open" and item["contested"]
    assert item["work_tag"]=="deferred"

def test_rejected_not_unselected_and_selected_requires_closed(ledger):
    s,p,u=create(ledger)
    with pytest.raises(Fault):
        change(s,p,u,[{"op":"option.add","key":"D000001","data":{"title":"Option","disposition":"rejected"}}],1,{"D000001":1},authority_refs=["operator"])
    change(s,p,u,[{"op":"option.add","key":"D000001","data":{"title":"Option"}}],1,{"D000001":1})
    assert s.children("alpha",u,p,"D000001","alternatives")["data"][0]["disposition"]=="unselected"

def test_cycles_rollback_whole_batch(ledger):
    s,p,u=ledger
    change(s,p,u,[{"op":"decision.create","data":{"title":"A","question":"A?"}},{"op":"decision.create","data":{"title":"B","question":"B?"}}])
    with pytest.raises(Fault,match="cycle"):
        change(s,p,u,[{"op":"link.add","key":"D000001","data":{"type":"depends_on","target_key":"D000002"}},
                       {"op":"link.add","key":"D000002","data":{"type":"depends_on","target_key":"D000001"}}],1,{"D000001":1,"D000002":1})
    assert s.children("alpha",u,p,"D000001","links")["data"]==[]

def test_supersession_requires_both_revisions(ledger):
    s,p,u=ledger
    change(s,p,u,[{"op":"decision.create","data":{"title":"Old","question":"Old?"}},{"op":"decision.create","data":{"title":"New","question":"New?"}}])
    change(s,p,u,[{"op":"decision.close","key":"D000002","data":{"answer":"New","rationale":"Better"}}],1,{"D000002":1},authority_refs=["operator"])
    with pytest.raises(Fault,match="revision"):
        change(s,p,u,[{"op":"decision.deprecate","key":"D000001","data":{"kind":"superseded","replacement_key":"D000002"}}],2,{"D000001":1},authority_refs=["operator"])
    change(s,p,u,[{"op":"decision.deprecate","key":"D000001","data":{"kind":"superseded","replacement_key":"D000002"}}],2,{"D000001":1,"D000002":2},authority_refs=["operator"])
    assert s.detail("alpha",u,p,"D000001")["data"]["status"]=="deprecated"
