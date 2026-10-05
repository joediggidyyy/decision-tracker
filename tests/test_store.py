import sqlite3
from uuid import uuid4
import pytest
from decision_tracker.models import Change
from decision_tracker.errors import Fault
from decision_tracker import store
from conftest import change

def test_durable_retry_precedes_stale_check(ledger):
    s,p,u=ledger
    req=Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason="Test",
               operations=[{"op":"decision.create","data":{"title":"First","question":"First?"}}])
    original=s.change("alpha",p,req)
    change(s,p,u,[{"op":"decision.create","data":{"title":"Second","question":"Second?"}}],1)
    replay=s.change("alpha",p,req)
    assert replay["replayed"] and replay["data"]==original["data"]
    req.reason="Changed"
    with pytest.raises(Fault,match="different"):s.change("alpha",p,req)

def test_dry_run_and_failed_batch_leave_no_receipt(ledger):
    s,p,u=ledger
    change(s,p,u,[{"op":"decision.create","data":{"title":"Draft","question":"Draft?"}}],validate_only=True)
    assert s.list_decisions("alpha",u,p)["revision"]==0
    with pytest.raises(Fault):
        change(s,p,u,[{"op":"decision.create","data":{"title":"A","question":"A?"}},{"op":"decision.lock","key":"D000001","data":{"baseline":"x"}}],authority_refs=["operator"])
    assert s.list_decisions("alpha",u,p)["data"]==[]

def test_history_is_immutable_and_asof_exact(ledger):
    s,p,u=ledger
    change(s,p,u,[{"op":"decision.create","data":{"title":"Before","question":"Question?"}}])
    change(s,p,u,[{"op":"decision.edit","key":"D000001","data":{"title":"After"}}],1,{"D000001":1})
    assert s.detail("alpha",u,p,"D000001",1)["data"]["title"]=="Before"
    with s.catalog.project("alpha",u,p,True) as (db,_):
        with pytest.raises(sqlite3.IntegrityError):db.execute("DELETE FROM transactions")
    assert len(s.history("alpha",u,p,"D000001")["data"])==2

def test_pagination_stale_and_literal_search(ledger):
    s,p,u=ledger
    change(s,p,u,[{"op":"decision.create","data":{"title":"100%","question":"Literal?"}},{"op":"decision.create","data":{"title":"Other","question":"Other?"}}])
    page=s.list_decisions("alpha",u,p,limit=1)
    assert page["next_cursor"] and not page["complete"]
    assert len(s.list_decisions("alpha",u,p,q="%")["data"])==1
    change(s,p,u,[{"op":"decision.edit","key":"D000001","data":{"title":"Changed"}}],1,{"D000001":1})
    with pytest.raises(Fault,match="changed"):s.list_decisions("alpha",u,p,cursor=page["next_cursor"])

def test_unicode_chunks_reconstruct(ledger):
    s,p,u=ledger
    value="ðŸ˜€"*5000
    change(s,p,u,[{"op":"decision.create","data":{"title":"Large","question":"Text?","answer":value}}])
    assert isinstance(s.detail("alpha",u,p,"D000001")["data"]["answer"],dict)
    output="";offset=0
    while True:
        result=s.field("alpha",u,p,"D000001","answer",1,offset,8192)["data"]
        output+=result["text"]
        if result["next_offset"] is None:break
        offset=result["next_offset"]
    assert output==value
