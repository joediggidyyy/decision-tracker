import subprocess,shutil
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from decision_tracker.api import create_app
from decision_tracker.config import Config
from decision_tracker.credentials import Credentials

def test_proposal_defaults():
    node=shutil.which('node');assert node
    path=Path(__file__).parents[1]/'src/decision_tracker/static/decision-form.js'
    script="""import {pathToFileURL} from 'node:url';import assert from 'node:assert/strict';
const {defaults,normalize}=await import(pathToFileURL(process.argv[1]).href);
const p={title:'Local storage',description:'Use the local drive',benefit:'Reliable locking',cost:'Separate backups'};
assert.deepEqual(defaults(p),{answer:p.description,rationale:'Expected benefit: Reliable locking\\n\\nCost or tradeoff: Separate backups',reason:'Recorded decision using proposal: Local storage.'});
assert.equal(defaults({title:'Manual',description:' ',benefit:'',cost:''}).rationale,'');
assert.equal(defaults({title:'Fallback',description:''}).answer,'Fallback');assert.equal(normalize(' x\\r\\ny '),'x\\ny');
console.log('proposal defaults passed');"""
    result=subprocess.run([node,'--input-type=module','-e',script,str(path)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr

def test_browser_request_recovery():
    path=Path(__file__).parents[1]/'src/decision_tracker/static/save-request.js'
    script="""import fs from 'node:fs';import assert from 'node:assert/strict';
const {sendRetained,definitive,readResponse}=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(process.argv[1],'utf8')).toString('base64'));
await assert.rejects(readResponse({json:async()=>{throw SyntaxError('parser internals');}}),/server response could not be read/);
const payload={request_id:'same',answer:'retained'};let calls=[],committed=false;const edit={pending:null};
const result=await sendRetained(edit,payload,async body=>{calls.push(body);if(!committed){committed=true;throw Error('Response lost');}return {replayed:true};});
assert.equal(result.replayed,true);assert.deepEqual(calls,[payload,payload]);
await assert.rejects(sendRetained(edit,{...payload,answer:'changed'},async()=>{}),/prior request/);
let count=0;const invalid=Object.assign(Error('Invalid date'),{code:'APPROVAL_DATE_FUTURE'});
await assert.rejects(sendRetained({pending:null},payload,async()=>{count++;throw invalid;}));assert.equal(count,1);assert.equal(definitive(invalid),true);
assert.equal(definitive(Error('Disconnected')),false);assert.equal(definitive({code:'INTERNAL_ERROR'}),false);
const frozen={pending:null};count=0;await assert.rejects(sendRetained(frozen,payload,async()=>{count++;throw Error('Disconnected');}));
assert.equal(count,2);assert.equal(frozen.pending,JSON.stringify(payload));console.log('Request recovery passed');"""
    result=subprocess.run([shutil.which('node'),'--input-type=module','-e',script,str(path)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr

def test_password_session_approval_through_http(tmp_path):
    credentials=Credentials(tmp_path/'auth.sqlite',initialize=True)
    credentials.redeem('bootstrap',credentials.issue('bootstrap'),'Synthetic approval password','Synthetic approval password')
    app=create_app(Config(data_root=str(tmp_path/'data'),auth_store=str(credentials.path),local_storage_confirmed=True))
    origin='http://127.0.0.1:8765'
    with TestClient(app,base_url=origin) as client:
        pre=client.get('/api/v1/session/setup').json()['data'];client.headers.update({'Origin':origin,'X-CSRF-Token':pre['csrf_token']})
        login=client.post('/api/v1/session',json={'password':'Synthetic approval password'});assert login.status_code==200
        client.headers['X-CSRF-Token']=login.json()['data']['csrf_token']
        project=client.post('/api/v1/projects',json={'project_id':'test','name':'Test','expected_catalog_revision':0,'request_id':str(uuid4())}).json()['data']
        client.headers['X-Ledger-UUID']=project['ledger_uuid'];url='/api/v1/projects/test'
        def send(ops,revision,expected):return client.post(url+'/changes',json={'expected_ledger_uuid':project['ledger_uuid'],'expected_revision':revision,'expected_decision_revisions':expected,'request_id':str(uuid4()),'reason':'Record decision','operations':ops})
        assert send([{'op':'decision.create','data':{'title':'Test','question':'What?'}}],0,{}).status_code==200
        invalid=send([{'op':'decision.close','key':'D000001','data':{'answer':'A','rationale':'B'}}],1,{'D000001':1});assert invalid.status_code==422
        valid=send([{'op':'decision.close','key':'D000001','data':{'answer':'A','rationale':'B','approval':{'mode':'authenticated_now'}}}],1,{'D000001':1});assert valid.status_code==200,valid.text
        detail=client.get(url+'/decisions/D000001').json()['data'];assert detail['latest_resolution_approval']['recorded_by']=='operator'
        assert client.get(url+'/decisions/D000001/approvals').json()['data'][0]['mode']=='authenticated_now'
        assert client.get('/api/v1/schema').json()['x-decision-tracker']['ledger_schemas']==[1,2,3,4]
