import secrets
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from decision_tracker.api import create_app
from decision_tracker.config import Config, PrincipalConfig
from decision_tracker.models import Change, ProjectChange
from decision_tracker.auth import Principal
from decision_tracker.service import Service

@pytest.fixture
def principal():
    return Principal("operator",frozenset({"*"}),frozenset({"read","write","decide","maintain","registry","propose"}))

@pytest.fixture
def ledger(tmp_path,principal):
    service=Service(tmp_path/"data")
    result=service.catalog.mutate(principal,ProjectChange(project_id="alpha",name="Alpha",expected_catalog_revision=0,request_id=uuid4()))
    return service,principal,result["data"]["ledger_uuid"]

def change(service,principal,uuid,ops,revision=0,expected=None,**extra):
    req=Change(expected_ledger_uuid=uuid,expected_revision=revision,
               expected_decision_revisions=expected or {},request_id=uuid4(),reason="Synthetic verification",
               operations=ops,**extra)
    return service.change("alpha",principal,req)

@pytest.fixture
def client(tmp_path):
    token=secrets.token_urlsafe(36)
    readonly=secrets.token_urlsafe(36)
    cfg=Config(data_root=str(tmp_path/"api"),local_storage_confirmed=True,principals=[
        PrincipalConfig(id="operator",token_env="DT_OPERATOR_TOKEN",projects=["*"],capabilities=["read","write","decide","maintain","registry","propose"]),
        PrincipalConfig(id="agent",token_env="DT_AGENT_TOKEN",projects=["alpha"],capabilities=["read"])])
    app=create_app(cfg,{"DT_OPERATOR_TOKEN":token,"DT_AGENT_TOKEN":readonly})
    with TestClient(app,base_url="http://127.0.0.1:8765") as c:
        c.headers["Authorization"]="Bearer "+token
        c.token=token;c.readonly=readonly
        yield c
