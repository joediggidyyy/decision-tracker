"""Real Chromium exercises isolated application data through native Calamum."""
import os, shutil, subprocess, threading, socket, time
from pathlib import Path
import uvicorn
from decision_tracker.api import create_app
from decision_tracker.config import Config
from decision_tracker.credentials import Credentials

def run_browser(tmp_path, script="action_browser.cjs", folder="action-browser"):

    credentials=Credentials(tmp_path/'auth.sqlite',initialize=True)
    password='Synthetic action form test password'
    credentials.redeem('bootstrap',credentials.issue('bootstrap'),password,password)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    app=create_app(Config(data_root=str(tmp_path/'data'),auth_store=str(credentials.path),local_storage_confirmed=True,port=port))
    if folder=='planning-link-browser':
        import json
        from uuid import uuid4
        from decision_tracker.auth import Principal
        from decision_tracker.models import Change,ProjectChange
        from decision_tracker.planning_links import PolicyChange,set_policy
        from decision_tracker.approval_api import Upgrade,upgrade
        s=app.state.service;p=Principal('fixture',frozenset({'*'}),frozenset({'read','write','decide','maintain','registry'}))
        u=s.catalog.mutate(p,ProjectChange(project_id='alpha',name='Planning-link review',expected_catalog_revision=0,request_id=uuid4()))['data']['ledger_uuid']
        s.change('alpha',p,Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason='Synthetic browser fixture',operations=[{'op':'decision.create','data':{'title':'Linked cycle','question':'Which approach?'}},{'op':'decision.create','data':{'title':'Replacement question','question':'What replaces the question?'}},{'op':'decision.create','data':{'title':'Omitted anchor','question':'Where is incorporation recorded?'}}]))
        s.change('alpha',p,Change(expected_ledger_uuid=u,expected_revision=1,expected_decision_revisions={'D000001':1,'D000003':1},request_id=uuid4(),reason='Fixture approved',authority_refs=['Synthetic owner approval'],operations=[{'op':'decision.close','key':'D000001','data':{'answer':'Approved approach','rationale':'Meets requirements'}},{'op':'decision.close','key':'D000003','data':{'answer':'Approved incorporation','rationale':'Synthetic optional-anchor branch'}}]))
        upgrade(app.state.artifacts,'alpha',u,p,Upgrade(expected_revision=2,request_id=uuid4()))
        planning=tmp_path/'planning';planning.mkdir()
        (planning/'plan.json').write_text(json.dumps({'schema_version':'codesentinel.canonical-document/v1','document_id':'test-plan','metadata':[{'label':'Version','value':'1.0'}],'sections':[{'id':'execution','heading':'Execution plan','blocks':[{'id':'execution-p0','type':'paragraph','text':'Approved approach'}]}]}),encoding='utf-8')
        nested=planning/'details';nested.mkdir();shutil.copy2(planning/'plan.json',nested/'detail.json')
        shutil.copy2(planning/'plan.json',planning/'qa-engine-planning-baseline-comparison-plan-20261003.json')
        (planning/'unsupported.json').write_text('{}',encoding='utf-8')
        set_policy(s,'alpha',u,p,PolicyChange(expected_policy_revision=0,request_id=uuid4(),reason='Owner registers fixture planning root',planning_roots=[str(planning)]))
        set_policy(s,'alpha',u,p,PolicyChange(expected_policy_revision=1,request_id=uuid4(),reason='Synthetic owner permits omitted anchor',anchor_required=False))
        s.change('alpha',p,Change(expected_ledger_uuid=u,expected_revision=2,expected_decision_revisions={'D000003':2},request_id=uuid4(),reason='Record incorporation without an anchor',operations=[{'op':'decision.link','key':'D000003','data':{'expected_policy_revision':2}}]))
        set_policy(s,'alpha',u,p,PolicyChange(expected_policy_revision=2,request_id=uuid4(),reason='Restore required fixture anchors',anchor_required=True))
    if folder=='projects-browser':
        from decision_tracker import store
        from decision_tracker.artifacts import Artifacts,bundle
        from decision_tracker.auth import Principal
        from uuid import uuid4
        principal=Principal('fixture',frozenset({'*'}),frozenset({'maintain','registry'}))
        for version,promote in ((1,True),(2,True),(2,False)):
            source=tmp_path/(str(uuid4())+'.sqlite');store.initialize(source,str(uuid4()),schema_version=version)
            with store.connect(source) as db:value=bundle(db)
            Artifacts(app.state.service).import_native(principal,value,promote)
    if folder=='legacy-browser':
        from legacy_fixture import request
        from decision_tracker.artifacts import Artifacts
        from decision_tracker.auth import Principal
        from decision_tracker.models import ProjectChange
        from uuid import uuid4
        p=Principal('fixture',frozenset({'*'}),frozenset({'read','write','decide','maintain','registry'}))
        r=Artifacts(app.state.service).import_native(p,request(),True)['data']
        app.state.service.catalog.mutate(p,ProjectChange(kind='register',project_id='legacy-test',name='Synthetic legacy',candidate_id=r['candidate_id'],expected_candidate_digest=r['logical_digest'],expected_catalog_revision=0,request_id=uuid4()))
    if folder=='project-details-browser':
        import json
        from uuid import uuid4
        from decision_tracker.auth import Principal
        from decision_tracker.models import Change,ProjectChange
        from decision_tracker.planning_links import PolicyChange,set_policy
        from decision_tracker.approval_api import Upgrade,upgrade
        s=app.state.service;p=Principal('fixture',frozenset({'*'}),frozenset({'read','write','decide','maintain','registry'}))
        u=s.catalog.mutate(p,ProjectChange(project_id='alpha',name='Project metadata and source context',expected_catalog_revision=0,request_id=uuid4()))['data']['ledger_uuid']
        s.catalog.mutate(p,ProjectChange(project_id='beta',name='Second project',expected_catalog_revision=1,request_id=uuid4()))
        for batch in range(3):
            s.change('alpha',p,Change(expected_ledger_uuid=u,expected_revision=batch,request_id=uuid4(),reason='Synthetic project overview',operations=[{'op':'decision.create','data':{'title':str(i),'question':'Which approach?'}} for i in range(batch*25,(batch+1)*25)]))
        s.change('alpha',p,Change(expected_ledger_uuid=u,expected_revision=3,expected_decision_revisions={'D000002':1},request_id=uuid4(),reason='Synthetic closure',authority_refs=['Synthetic approval'],operations=[{'op':'decision.close','key':'D000002','data':{'answer':'Chosen','rationale':'Reviewed'}}]))
        s.change('alpha',p,Change(expected_ledger_uuid=u,expected_revision=4,expected_decision_revisions={'D000001':1,'D000002':2},request_id=uuid4(),reason='Synthetic deprecation',authority_refs=['Synthetic approval'],operations=[{'op':'decision.deprecate','key':'D000001','data':{'kind':'superseded','replacement_key':'D000002'}}]))
        upgrade(app.state.artifacts,'alpha',u,p,Upgrade(expected_revision=5,request_id=uuid4()))
        roots=[]
        for name in ['first','second']:
            path=tmp_path/name;path.mkdir();roots.append(str(path))
            (path/'plan.json').write_text(json.dumps({'schema_version':'codesentinel.canonical-document/v1','document_id':name,'metadata':[{'label':'Version','value':'1.0'}],'sections':[{'id':'scope','heading':'Scope','blocks':[{'id':'scope-p1','type':'paragraph','text':'Synthetic source'}]}]}),encoding='utf-8')
        set_policy(s,'alpha',u,p,PolicyChange(expected_policy_revision=0,request_id=uuid4(),reason='Synthetic source roots',planning_roots=roots))
    if folder=='record-display-browser':
        from uuid import uuid4
        from dataclasses import replace
        from decision_tracker.auth import Principal
        from decision_tracker.models import Change,ProjectChange
        from decision_tracker.approval_api import Upgrade,upgrade
        s=app.state.service;p=Principal('fixture',frozenset({'*'}),frozenset({'read','write','decide','maintain','registry'}))
        u=s.catalog.mutate(p,ProjectChange(project_id='alpha',name='Decision display review',expected_catalog_revision=0,request_id=uuid4()))['data']['ledger_uuid']
        def change(ops,principal=p):
            revision=s.list_decisions('alpha',u,p)['revision']
            affected={op['key'] for op in ops if op.get('key','').startswith('D')}|{op['data']['target_key'] for op in ops if op.get('data',{}).get('target_key')}
            keys={key:s.detail('alpha',u,p,key)['data']['revision'] for key in affected}
            return s.change('alpha',principal,Change(expected_ledger_uuid=u,expected_revision=revision,expected_decision_revisions=keys,request_id=uuid4(),reason='Synthetic display fixture',authority_refs=[] if any(op['op']=='decision.deprecate' and 'approval' in op.get('data',{}) for op in ops) else ['Synthetic authority'],operations=ops))
        change([{'op':'decision.create','data':{'title':title,'question':'Which approach preserves café, Δ and <literal> text?\n\nKeep this paragraph.','answer':'Draft answer — retained.','rationale':'First reason.\n\nSecond reason.'}} for title in ['Working decision','Reported approval','Protected decision','Empty supporting sections','Deprecated decision','Long record']])
        upgrade(app.state.artifacts,'alpha',u,p,Upgrade(expected_revision=1,request_id=uuid4()))
        change([{'op':'decision.edit','key':'D000001','data':{'evidence_state':{'implementation':{'status':'In progress, not accepted','responsible_role':'Engineering','evidence_refs':['docs/first.md','docs/second.md']},'verification':None,'acceptance':{'status':'Awaiting owner','evidence_refs':[]}}}},
                {'op':'option.add','key':'D000001','data':{'title':'Local choice','description':'Use local files.\n\nRetain original bytes.','benefit':'Predictable custody','cost':'Backup required'}},
                {'op':'reference.add','key':'D000001','data':{'label':'Design source','locator':'docs/'+('long-path/'*12)+'design.md','availability':'unknown','authenticity':'unverified','limitations':'Review pending'}},
                {'op':'link.add','key':'D000001','data':{'target_key':'D000002','type':'relates_to'}},
                {'op':'link.add','key':'D000004','data':{'target_key':'D000001','type':'relates_to'}}])
        approval={'mode':'reported','approver':'Owner','precision':'date','occurred_date':'2020-01-02','utc_offset_minutes':-300,'sources':['Synthetic meeting note']}
        change([{'op':'decision.close','key':'D000002','data':{'answer':'Approved approach','rationale':'Reviewed','approval':approval}}])
        human=replace(p,auth_method='human_password_session')
        change([{'op':'decision.close','key':'D000003','data':{'answer':'Protected approach','rationale':'Reviewed','approval':{'mode':'authenticated_now'}}}],human)
        change([{'op':'decision.lock','key':'D000003','data':{'baseline':'Display fixture baseline'}}])
        change([{'op':'decision.deprecate','key':'D000005','data':{'kind':'obsolete','approval':approval}}])
        change([{'op':'decision.edit','key':'D000006','data':{'answer':('Long paragraph café Δ — exact text.\n\n'*450),'rationale':'End of long record.'}}])
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.05)
        assert server.started
        root=Path(__file__).parents[1]
        output=root/'.local'/folder;output.mkdir(parents=True,exist_ok=True)
        extra=[str(tmp_path/'planning'/'plan.json')] if folder=='planning-link-browser' else []
        try:
            result=subprocess.run([shutil.which('node'),str(root/'tests'/script),f'http://127.0.0.1:{port}',str(output),*extra],capture_output=True,text=True,encoding="utf-8",timeout=180,env=os.environ.copy())
        except subprocess.TimeoutExpired as exc:
            for capture in (exc.stdout,exc.stderr):
                if capture: print(capture.decode('utf-8',errors='replace') if isinstance(capture,bytes) else capture)
            raise
        print(result.stdout)
        assert result.returncode==0,result.stdout+result.stderr
    finally:
        server.should_exit=True;thread.join(10)
        assert not thread.is_alive()


def test_action_forms_browser(tmp_path):
    run_browser(tmp_path)


def test_closed_context_browser(tmp_path):
    run_browser(tmp_path, 'closed_context_browser.cjs', 'closed-context-browser')
