from uuid import uuid4

def setup_project(client):
    r=client.post("/api/v1/projects",json={"project_id":"alpha","name":"Alpha","expected_catalog_revision":0,"request_id":str(uuid4())})
    assert r.status_code==200,r.text
    u=r.json()["data"]["ledger_uuid"]
    client.headers["X-Ledger-UUID"]=u
    return u

def test_authenticated_create_read_conflict(client):
    u=setup_project(client)
    payload={"expected_ledger_uuid":u,"expected_revision":0,"request_id":str(uuid4()),"reason":"Test",
             "operations":[{"op":"decision.create","data":{"title":"Browser record","question":"Can edit?"}}]}
    r=client.post("/api/v1/projects/alpha/changes",json=payload)
    assert r.status_code==200,r.text
    assert client.get("/api/v1/projects/alpha/decisions/D000001").json()["data"]["title"]=="Browser record"
    payload["request_id"]=str(uuid4())
    assert client.post("/api/v1/projects/alpha/changes",json=payload).status_code==409
    client.headers["X-Ledger-UUID"]=str(uuid4())
    assert client.get("/api/v1/projects/alpha/decisions").status_code==409

def test_readonly_and_nonexistent_project(client):
    u=setup_project(client)
    client.headers["Authorization"]="Bearer "+client.readonly
    assert client.get("/api/v1/projects/alpha/decisions").status_code==200
    payload={"expected_ledger_uuid":u,"expected_revision":0,"request_id":str(uuid4()),"reason":"Test","operations":[{"op":"decision.create","data":{"title":"X","question":"X?"}}]}
    assert client.post("/api/v1/projects/alpha/changes",json=payload).status_code==403
    assert client.get("/api/v1/projects/other/decisions").status_code==404

def test_cookie_csrf_and_logout(client):
    setup_project(client)
    token=client.token
    client.headers.pop("Authorization")
    r=client.post("/api/v1/session",headers={"Origin":"http://127.0.0.1:8765"},json={"token":token})
    assert r.status_code==200,r.text
    csrf=r.json()["data"]["csrf_token"]
    assert client.delete("/api/v1/session").status_code==403
    assert client.delete("/api/v1/session",headers={"Origin":"http://127.0.0.1:8765","X-CSRF-Token":csrf}).status_code==200
    assert client.get("/api/v1/projects").status_code==401

def test_origin_host_input_and_headers(client):
    assert client.get("/api/v1/status",headers={"Origin":"https://attacker.invalid"}).status_code==403
    assert client.get("/api/v1/status",headers={"Host":"attacker.invalid"}).status_code==403
    response=client.get("/api/v1/status")
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.post("/api/v1/projects",json={"unknown":"value"}).status_code==422
    assert client.post("/api/v1/projects",content="{}",headers={"Content-Type":"text/plain"}).status_code==422
