import json
from uuid import uuid4
import pytest
from decision_tracker import cli
from decision_tracker.models import Change
from decision_tracker.errors import Fault

@pytest.mark.parametrize("group,action,data",[
 ("decision","create",{"title":"X","question":"X?"}),
 ("decision","edit",{"title":"Y"}),("decision","edit-resolution",{"answer":"A","rationale":"R","selected_option":None}),
 ("decision","close",{"answer":"A","rationale":"R"}),("decision","reopen",{"impact":"Review"}),
 ("decision","lock",{"baseline":"v1"}),("decision","amend",{"title":"A","question":"Q","impact":"I","baseline_disposition":"continue"}),
 ("decision","deprecate",{"kind":"obsolete"}),("decision","defer",{"resume_trigger":"Next"}),
 ("decision","resume",{}),("decision","challenge",{}),("decision","resolve-challenge",{}),
 ("decision","set-work",{"work_tag":"under-investigation"}),
 ("option","add",{"title":"A"}),("option","edit",{"title":"B"}),("option","retire",{}),
 ("reference","add",{"label":"Source","locator":"synthetic:source"}),("reference","edit",{"label":"Edited"}),
 ("reference","retire",{}),("link","add",{"target_key":"D000002","type":"relates_to"}),("link","unlink",{})
])
def test_every_mutation_command_builds_valid_shared_envelope(monkeypatch,tmp_path,group,action,data,capsys):
 path=tmp_path/"input.json";path.write_text(json.dumps(data),encoding="utf-8")
 monkeypatch.setenv("DT_OPERATOR_TOKEN","synthetic-cli-only-credential-123456789")
 captured=[]
 def request(self,method,path,data=None,uuid=None,download=None):
  captured.append((method,path,Change.model_validate(data),uuid));return {"ok":True,"data":[]}
 monkeypatch.setattr(cli.Client,"request",request)
 uuid=str(uuid4())
 assert cli.main([group,action,"--json","--project","alpha","--ledger-uuid",uuid,"--expected-revision","2","--record-revision","1","--key","D000001","--id",str(uuid4()),"--reason","Synthetic command mapping","--request-id",str(uuid4()),"--input",str(path),"--dry-run"])==0
 output=json.loads(capsys.readouterr().out);assert output["ok"]
 method,route,request,binding=captured[0]
 assert method=="POST" and route.endswith("/changes") and request.validate_only and binding==uuid
 assert request.operations[0].op==group+"."+action and request.operations[0].data==data

def test_exit_codes_and_no_secret_echo(monkeypatch,capsys):
 monkeypatch.delenv("DT_OPERATOR_TOKEN",raising=False)
 assert cli.main(["service","status","--json"])==4
 output=capsys.readouterr().out
 assert json.loads(output)["error"]["code"]=="UNAUTHORIZED"
 assert cli.exit_code({"ok":False,"error":{"code":"STALE_REVISION"}})==3
 assert cli.exit_code({"ok":False,"error":{"code":"RETRY_LATER"}})==5
