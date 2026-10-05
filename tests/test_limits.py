import pytest
from decision_tracker.errors import Fault
from decision_tracker.artifacts import Artifacts
from conftest import change

def test_capacity_and_aggregate_are_write_boundaries(ledger):
 s,p,u=ledger
 for i in range(20):
  change(s,p,u,[{"op":"decision.create","data":{"title":str(i*25+n),"question":"Capacity?"}} for n in range(25)],i)
 with pytest.raises(Fault,match="capacity"):
  change(s,p,u,[{"op":"decision.create","data":{"title":"Overflow","question":"Rejected?"}}],20)
 page=s.list_decisions("alpha",u,p,limit=200)
 assert len(page["data"])==200 and not page["complete"]
 assert s.list_decisions("alpha",u,p,cursor=page["next_cursor"],limit=200)["revision"]==20
 assert Artifacts(s).verify("alpha",u,p)["data"]["integrity"]=="ok"

def test_resolution_selection_and_reopen_impact_are_audited(ledger):
 s,p,u=ledger
 change(s,p,u,[{"op":"decision.create","data":{"title":"Choice","question":"Which?"}}])
 change(s,p,u,[{"op":"option.add","key":"D000001","data":{"title":"One"}},{"op":"option.add","key":"D000001","data":{"title":"Two"}}],1,{"D000001":1})
 options=s.children("alpha",u,p,"D000001","alternatives")["data"]
 first,second=[x["id"] for x in options]
 change(s,p,u,[{"op":"decision.close","key":"D000001","data":{"answer":"One","rationale":"Reason","selected_option":first}}],2,{"D000001":2},authority_refs=["synthetic"])
 with pytest.raises(Fault):
  change(s,p,u,[{"op":"option.edit","key":"D000001","id":second,"data":{"disposition":"selected"}}],3,{"D000001":3},authority_refs=["synthetic"])
 change(s,p,u,[{"op":"decision.edit-resolution","key":"D000001","data":{"answer":"Two","selected_option":second}}],3,{"D000001":3},authority_refs=["synthetic"])
 selected=[x for x in s.children("alpha",u,p,"D000001","alternatives")["data"] if x["disposition"]=="selected"]
 assert selected[0]["id"]==second
 change(s,p,u,[{"op":"decision.reopen","key":"D000001","data":{"impact":"Reevaluate compatibility"}}],4,{"D000001":4},authority_refs=["synthetic"])
 from decision_tracker import store
 with s.catalog.project("alpha",u,p) as (db,_):
  tx=store.unpack(db.execute("SELECT * FROM transactions WHERE ledger_revision=5").fetchone())
  assert tx["request_json"]["operations"][0]["data"]["impact"]=="Reevaluate compatibility"
 assert Artifacts(s).verify("alpha",u,p)["revision"]==5
