"""Decision Tracker CLI: every data operation uses the shared HTTP API."""
import argparse
import http.client
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode, urlsplit
from .config import load_config
from .models import Change, ProjectChange, ProjectState
from .errors import Fault, require
from .store import encode

DECISIONS=["list","get","create","edit","edit-resolution","close","reopen","lock","amend","deprecate",
           "defer","resume","challenge","resolve-challenge","set-work","history","as-of","field","link","planning-links","apply","applications"]

def common(parser,suppress=True):
    default=argparse.SUPPRESS if suppress else None
    for name in ["base-url","config","project","ledger-uuid","token-env","input","request-id","reason",
                 "expected-decision-revisions","binding","deployment","credential-principal","principal","token-id"]:
        parser.add_argument("--"+name,default=default)
    for name in ["expected-revision","expected-catalog-revision","record-revision","expected-policy-revision"]:
        parser.add_argument("--"+name,type=int,default=default)
    parser.add_argument("--json",action="store_true",default=argparse.SUPPRESS if suppress else False)
    parser.add_argument("--dry-run",action="store_true",default=argparse.SUPPRESS if suppress else False)
    parser.add_argument("--authority-ref",action="append",default=argparse.SUPPRESS if suppress else [])
    for name in ('saved-id','group-id'):
        parser.add_argument('--'+name,action='append',default=argparse.SUPPRESS if suppress else [])
    for name in ["key","id","name","relative-path","title","question","answer","rationale","owner-role","baseline",
                 "work-tag","resume-trigger","kind","replacement-key","target-key","type","impact","baseline-disposition",
                 "selected-option","cursor","q","status","work","owner","artifact-id","output","bind","candidate-id","expected-candidate-digest","order"]:
        parser.add_argument("--"+name,default=default)
    parser.add_argument("--prompt-code",action="store_true",default=argparse.SUPPRESS if suppress else False)
    parser.add_argument("--store-local",action="store_true",default=argparse.SUPPRESS if suppress else False)
    parser.add_argument("--limit",type=int,default=argparse.SUPPRESS if suppress else 50)
    parser.add_argument("--port",type=int,default=default)
    parser.add_argument("--data-root",default=default)
    parser.add_argument("--revision",type=int,default=default)
    parser.add_argument("--offset",type=int,default=argparse.SUPPRESS if suppress else 0)
    parser.add_argument("--field",default=default)
    for name in ('planning-document','planning-section','expected-document-sha256','expected-projection-sha256','expected-resolution-id'):
        parser.add_argument('--'+name,default=default)
    parser.add_argument('--anchor-required',choices=('true','false'),default=default)
    parser.add_argument('--planning-root',dest='planning_roots',action='append',default=default)
    for name in ('source-namespace','source-id','source-version','payload','legacy-kind'):
        parser.add_argument('--'+name,default=default)
    parser.add_argument('--origin',choices=('native','legacy'),default=default)
    parser.add_argument('--relations',action='store_true',default=argparse.SUPPRESS if suppress else False)

def parser():
    root=argparse.ArgumentParser(prog="decision-tracker",description=__doc__,
        epilog="Use --input FILE (or - for stdin) for structured fields. Mutations require explicit revision, request ID and reason. Agent credentials use an explicit environment variable or protected local principal.")
    common(root,False)
    groups=root.add_subparsers(dest="group",required=True)
    definitions={
        "service":["serve","status","catalog-backup","ensure-running","open","install-launcher","uninstall-launcher","configure-credentials","stop"],
        "auth":["setup-code","recover","reset-password","migrate","token"],
        "project":["list","show","create","register","disable","enable","policy"],
        "decision":DECISIONS,
        "option":["add","list","edit","retire"],
        "reference":["add","list","edit","retire"],
        "link":["add","list","unlink"],
        "query":["search","context","impact","deprecated"],
        "change":["apply"],
        "data":["export","import-validate","import-new","candidates","prepare-candidate","backup","verify","restore-check","artifact-list","artifact-download","upgrade-check","upgrade",
                "saved-list","saved-get","saved-create","saved-edit","saved-delete","saved-group-create","saved-group-edit","saved-group-delete","saved-stage","saved-prepare","saved-publish","saved-export","saved-import","saved-import-check","saved-backup","saved-backup-check","saved-backup-download"]}
    for group,verbs in definitions.items():
        parent=groups.add_parser(group,help=group+" operations")
        children=parent.add_subparsers(dest="action",required=True)
        for verb in verbs:
            description = "Withdrawn for new writes. Reopen, edit the open decision, then Close. Historical receipts still replay." if group=="decision" and verb=="edit-resolution" else f"{group} {verb}; use the shared versioned API. Closed records require reopening before ordinary edits. Reopening must commit separately."
            if group=='decision' and verb in ('apply','applications'):
                description='Compatibility alias; use decision '+('link' if verb=='apply' else 'planning-links')+'. Existing request IDs and payloads must remain unchanged for retries.'
            if group=='decision' and verb=='link':
                description='Link an already incorporated closed resolution to authoritative planning. Records evidence; does not edit planning or mark implementation complete.'
            child=children.add_parser(verb,description=description)
            common(child)
            if group=='project' and verb=='policy':
                actions=child.add_subparsers(dest='policy_action',required=True)
                for action in ('show','set'):common(actions.add_parser(action))
            if group=='auth' and verb=='token':
                token_actions=child.add_subparsers(dest='token_action',required=True)
                for action in ('create','rotate','revoke','list'):common(token_actions.add_parser(action))
    return root

def read_input(path):
    if not path:return {}
    if path!="-":require(Path(path).stat().st_size<=10*1024*1024,"LIMIT_EXCEEDED","Input exceeds10MiB.",413)
    raw=sys.stdin.read(10*1024*1024+1) if path=="-" else Path(path).read_text(encoding="utf-8")
    require(len(raw.encode())<=10*1024*1024,"LIMIT_EXCEEDED","Input exceeds10MiB.",413)
    try:
        from .legacy import parse
        parse(raw)  # Reject duplicate members before the ordinary object parser.
        value=json.loads(raw)
    except ValueError:raise Fault("VALIDATION_ERROR","Input is not valid JSON.") from None
    require(isinstance(value,dict),"VALIDATION_ERROR","Input must be a JSON object.")
    return value

class Client:
    def __init__(self,base,token):
        parsed=urlsplit(base)
        require(parsed.scheme=="http" and parsed.hostname in ("127.0.0.1","localhost") and not parsed.username
                and not parsed.password and parsed.path in ("","/") and not parsed.query and not parsed.fragment,
                "FORBIDDEN","Client credentials can only be sent to local loopback HTTP.",403)
        self.host,self.port,self.token=parsed.hostname,parsed.port or 8765,token

    def request(self,method,path,data=None,uuid=None,download=None):
        connection=http.client.HTTPConnection(self.host,self.port,timeout=3)
        headers={"Authorization":"Bearer "+self.token,"Content-Type":"application/json"}
        if uuid:headers["X-Ledger-UUID"]=uuid
        try:
            connection.connect()
            connection.sock.settimeout(60 if any(x in path for x in ("backup","import","export","restore")) else 30)
            connection.request(method,path,body=encode(data).encode() if data is not None else None,headers=headers)
            response=connection.getresponse()
            cap=20*1024*1024 if download or path.startswith('/api/v1/saved-decisions/') else 65536
            raw=response.read(cap+1)
            require(len(raw)<=cap,"LIMIT_EXCEEDED","Response exceeds client limit.",413)
            if download and response.status==200:
                target=Path(download)
                with target.open("xb") as out:out.write(raw)
                return {"ok":True,"data":{"saved":str(target),"bytes":len(raw)}}
            try:value=json.loads(raw)
            except ValueError:raise Fault("SERVICE_UNAVAILABLE","Service returned an invalid response.",503) from None
            return value
        except (OSError,http.client.HTTPException):
            raise Fault("SERVICE_UNAVAILABLE","The service connection failed or the write outcome is unknown.",503,
                        recovery="Check service status. For uncertain writes retry the identical request ID and body.") from None
        finally:connection.close()

def execute(args):
    is_change=args.group=="change" or (args.group in ("decision","option","reference","link") and args.action not in ("list","get","history","as-of","field","planning-links","applications"))
    require(not args.dry_run or is_change,"VALIDATION_ERROR","Dry-run is supported only for decision change operations.")
    if args.group=='auth' or args.group=='service' and args.action in ('ensure-running','open','install-launcher','uninstall-launcher','configure-credentials','stop') or args.group=='project' and args.action=='policy' and args.policy_action=='set':
        from .local_cli import execute as local_execute
        return local_execute(args)
    cfg=load_config(args.config) if args.config else None
    if args.group=="service" and args.action=="serve":
        require(cfg is not None,"VALIDATION_ERROR","service serve requires --config.")
        if args.port is not None:cfg.port=args.port
        if args.data_root is not None:cfg.data_root=args.data_root
        from .api import create_app
        import uvicorn
        cfg.managed_idle=False
        app=create_app(cfg)
        server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=cfg.port,workers=1,access_log=False,proxy_headers=False,timeout_graceful_shutdown=5))
        app.state.shutdown=lambda:setattr(server,"should_exit",True)
        server.run()
        return {"ok":True,"data":{"service":"stopped"}}
    token_name=args.token_env or "DT_OPERATOR_TOKEN"
    require(not (args.credential_principal and args.token_env),'VALIDATION_ERROR','Choose token environment or stored principal, not both.')
    token=os.environ.get(token_name,"")
    if args.credential_principal:
        from .deployment import load,default_path,probe
        from .windows_local import read_bundle
        deployment,dcfg=load(args.deployment or default_path());bundle=read_bundle(Path(deployment['bundle']))
        require(args.credential_principal!='operator','FORBIDDEN','Select an agent principal.',403)
        require(args.credential_principal in {p.id for p in dcfg.principals},'FORBIDDEN','Unknown agent principal.',403)
        require(not args.base_url or args.base_url.rstrip('/')==f'http://127.0.0.1:{dcfg.port}','FORBIDDEN','Stored credentials are bound to this deployment.',403)
        require(probe(deployment,dcfg,bundle['control_key']) is not None,'SERVICE_UNAVAILABLE','Start the service before accessing it.',503)
        token=bundle.get('tokens',{}).get(args.credential_principal,'');cfg=dcfg
    require(bool(token),"UNAUTHORIZED","Inject the configured client credential.",401,variable=token_name)
    base=args.base_url or f"http://127.0.0.1:{cfg.port if cfg else 8765}"
    client=Client(base,token);g,a=args.group,args.action
    if g=="service":return client.request("GET" if a=="status" else "POST","/api/v1/status" if a=="status" else "/api/v1/catalog/backups",{} if a!="status" else None)
    data=read_input(args.input)
    if g=='data' and a.startswith('saved-'):
        from .saved_decisions import SavedChange, Selection, Staged, Bundle
        endpoint='/api/v1/saved-decisions'
        if a=='saved-list':
            return client.request('GET',endpoint+'?'+urlencode({'offset':args.offset,'limit':min(args.limit,50),**({'expected_revision':args.expected_revision} if args.expected_revision is not None else {})}))
        if a=='saved-get':
            require(args.id,'VALIDATION_ERROR','Supply --id.')
            return client.request('GET',endpoint+'/'+str(__import__('uuid').UUID(args.id)))
        if a=='saved-export':
            return client.request('POST',endpoint+'/export',{},download=args.output)
        if a=='saved-backup-download':
            require(args.artifact_id and args.output,'VALIDATION_ERROR','Supply --artifact-id and --output.')
            return client.request('GET',endpoint+'/backups/'+str(__import__('uuid').UUID(args.artifact_id))+'/content',download=args.output)
        if a in ('saved-backup','saved-backup-check'):
            return client.request('POST',endpoint+'/'+('backup' if a=='saved-backup' else 'backup-check'),{} if a=='saved-backup' else {'artifact_id':args.artifact_id or data.get('artifact_id')})
        if a=='saved-import-check':return client.request('POST',endpoint+'/import-check',Bundle.model_validate(data).model_dump(mode='json'))
        if a=='saved-stage':
            value=Selection.model_validate({**data,**({'expected_revision':args.expected_revision} if args.expected_revision is not None else {}),
                **({'decision_ids':args.saved_id} if args.saved_id else {}),**({'group_ids':args.group_id} if args.group_id else {})})
            result=client.request('POST',endpoint+'/stage',value.model_dump(mode='json'))
            if args.output and result.get('ok'):Path(args.output).write_text(encode(result),encoding='utf-8')
            return result
        if a=='saved-prepare':
            contents=data.get('decisions') or [x['content'] for x in data.get('data',[])]
            require(args.project and args.ledger_uuid and args.expected_revision is not None and args.request_id and args.reason,'VALIDATION_ERROR','For publication supply project, ledger UUID, expected revision, request ID and reason.')
            staged=Staged(decisions=contents,project_id=args.project,ledger_uuid=args.ledger_uuid,
                          expected_revision=args.expected_revision,publication_id=args.request_id,reason=args.reason,approval=data.get('approval'))
            result=client.request('POST',endpoint+'/prepare',staged.model_dump(mode='json'))
            if result.get('ok'):
                result['data'].update(decisions=[x.model_dump(mode='json') for x in staged.decisions],reason=args.reason,
                                      index=0,targets={},receipts=[],revision=args.expected_revision)
            if args.output and result.get('ok'):
                with Path(args.output).open('x',encoding='utf-8') as file:file.write(encode(result))
            return result
        if a=='saved-publish':
            require(args.input and args.input!='-','VALIDATION_ERROR','Publish a retained preparation file with --input FILE.')
            prepared=data.get('data',data)
            require(args.project and prepared.get('project_id')==args.project and args.ledger_uuid,'LEDGER_IDENTITY_MISMATCH','Supply the preparation project and ledger UUID.',409)
            if prepared.get('format')=='decision-tracker.saved-publication/v2':
                require(prepared.get('ledger_uuid')==args.ledger_uuid,'LEDGER_IDENTITY_MISMATCH','Preparation UUID differs from binding.',409)
                path=Path(args.input)
                def checkpoint():
                    temporary=path.with_name(path.name+'.pending')
                    with temporary.open('x',encoding='utf-8') as file:
                        file.write(encode({'ok':True,'data':prepared}));file.flush();os.fsync(file.fileno())
                    temporary.replace(path)
                while prepared['phase']!='done':
                    if not prepared.get('requests'):
                        body=Staged(decisions=prepared['decisions'],project_id=args.project,ledger_uuid=args.ledger_uuid,
                                    expected_revision=prepared['revision'],publication_id=prepared['publication_id'],
                                    phase=prepared['phase'],targets=prepared['targets'],approval=prepared['approval'],reason=prepared['reason'])
                        result=client.request('POST',endpoint+'/prepare',body.model_dump(mode='json'))
                        if not result.get('ok'):return {**result,'publication_phase':prepared['phase'],'receipts':prepared['receipts']}
                        prepared['requests']=result['data']['requests'];checkpoint()
                    while prepared['index']<len(prepared['requests']):
                        req=Change.model_validate(prepared['requests'][prepared['index']])
                        receipt=client.request('POST','/api/v1/projects/'+args.project+'/changes',req.model_dump(mode='json'),args.ledger_uuid)
                        if not receipt.get('ok'):return {**receipt,'publication_phase':prepared['phase'],'receipts':prepared['receipts']}
                        prepared['receipts'].append(receipt);prepared['revision']=receipt['revision']
                        for row in receipt['data']:prepared['targets'][row['key']]=row['revision']
                        prepared['index']+=1;checkpoint()
                    prepared['phase']={'create':'close','close':'protect','protect':'done'}[prepared['phase']]
                    prepared['requests']=[];prepared['index']=0;checkpoint()
                return {'ok':True,'data':{'publication_phase':'done','closed_protected':len(prepared['targets']),'receipts':prepared['receipts']}}
            requests=prepared.get('requests',[])
            require(bool(requests),'VALIDATION_ERROR','Preparation contains no requests.')
            completed=[]
            for item in requests:
                req=Change.model_validate(item)
                require(str(req.expected_ledger_uuid)==args.ledger_uuid,'LEDGER_IDENTITY_MISMATCH','Preparation UUID differs from binding.',409)
                receipt=client.request('POST','/api/v1/projects/'+args.project+'/changes',req.model_dump(mode='json'),args.ledger_uuid)
                if not receipt.get('ok'):return {**receipt,'completed_batches':len(completed),'total_batches':len(requests),'receipts':completed}
                completed.append(receipt)
            return {'ok':True,'data':{'completed_batches':len(completed),'receipts':completed,'publication_mode':'legacy-create-only'}}
        action={'saved-create':'save','saved-edit':'save','saved-delete':'delete','saved-group-create':'group-save','saved-group-edit':'group-save','saved-group-delete':'group-delete','saved-import':'import'}[a]
        value={'action':action,'expected_revision':args.expected_revision if args.expected_revision is not None else data.get('expected_revision'),
               'request_id':args.request_id or data.get('request_id'),'reason':args.reason or data.get('reason')}
        if a=='saved-import':value['bundle']=data.get('bundle',data)
        else:
            if args.id or data.get('id'):value['id']=args.id or data['id']
            if a in ('saved-edit','saved-delete','saved-group-edit','saved-group-delete'):
                require(value.get('id'),'VALIDATION_ERROR','Supply --id for the item to change.')
            if action=='save':
                content=data.get('content',{})
                content.update({k:getattr(args,k) for k in ('title','question','answer','rationale','owner_role') if getattr(args,k) is not None})
                if a=='saved-edit' and content:
                    current=client.request('GET',endpoint+'/'+str(__import__('uuid').UUID(value['id'])))
                    if not current.get('ok'):return current
                    content={**current['data']['content'],**content}
                if content:value['content']=content
                if args.group_id or 'group_ids' in data:value['group_ids']=args.group_id or data['group_ids']
            if action=='group-save':value['name']=args.name or data.get('name')
        return client.request('POST',endpoint+'/changes',SavedChange.model_validate(value).model_dump(mode='json'))
    uuid=args.ledger_uuid
    if args.binding:
        binding=read_input(args.binding)
        require(binding.get("project_id")==args.project,"LEDGER_IDENTITY_MISMATCH","Binding belongs to another project.",409)
        uuid=uuid or binding.get("ledger_uuid")
    if g=="data" and a in ("import-validate","import-new"):
        return client.request("POST","/api/v1/imports/"+("new" if a=="import-new" else "validate"),data)
    if g=="project" and a=="list":return client.request("GET","/api/v1/projects")
    if g=="data" and a=="candidates":
        return client.request("GET","/api/v1/candidates?"+urlencode({k:v for k,v in {'cursor':args.cursor,'limit':args.limit}.items() if v is not None}))
    if g=="data" and a=="prepare-candidate":
        from uuid import UUID
        try: candidate=str(UUID(args.candidate_id or data.get('candidate_id','')))
        except (ValueError,TypeError):raise Fault('VALIDATION_ERROR','Supply a valid --candidate-id.') from None
        return client.request("POST","/api/v1/candidates/"+candidate+"/prepare",{})
    if g=='data' and a in ('export','backup','verify','restore-check','artifact-download') and args.candidate_id:
        from uuid import UUID
        try:candidate=str(UUID(args.candidate_id))
        except ValueError:raise Fault('VALIDATION_ERROR','Invalid candidate ID.') from None
        require(args.expected_candidate_digest,'VALIDATION_ERROR','Supply --expected-candidate-digest.')
        prefix='/api/v1/candidates/'+candidate
        if a=='artifact-download':
            require(args.artifact_id and args.output,'VALIDATION_ERROR','Supply artifact ID and output.')
            return client.request('GET',prefix+'/artifacts/'+args.artifact_id+'/content?'+urlencode({'expected_candidate_digest':args.expected_candidate_digest}),download=args.output)
        body={'expected_candidate_digest':args.expected_candidate_digest}
        if a=='restore-check':body['artifact_id']=args.artifact_id or data.get('artifact_id')
        return client.request('POST',prefix+'/'+{'export':'exports','backup':'backups','verify':'verify','restore-check':'restore-check'}[a],body)
    require(args.project is not None,"VALIDATION_ERROR","Supply --project.")
    import re
    require(re.fullmatch(r"[a-z][a-z0-9-]{0,47}",args.project) is not None,"VALIDATION_ERROR","Invalid project ID.")
    path="/api/v1/projects/"+args.project
    if g=="project":
        if a=='policy':
            require(uuid,'VALIDATION_ERROR','Supply --ledger-uuid or a matching --binding.')
            return client.request('GET',path+'/policy',uuid=uuid)
        if a=="show":
            value=client.request("GET",path,uuid=uuid)
            if args.bind and value.get("ok"):
                with Path(args.bind).open("x",encoding="utf-8") as out:
                    out.write(encode({k:value["data"][k] for k in ("project_id","ledger_uuid")}))
            return value
        if a in ("create","register"):
            value={**data,"kind":a,"project_id":args.project,"name":args.name or data.get("name"),
                   "expected_catalog_revision":args.expected_catalog_revision if args.expected_catalog_revision is not None else data.get("expected_catalog_revision"),
                   "request_id":args.request_id or data.get("request_id")}
            if args.relative_path:value["relative_path"]=args.relative_path
            if args.candidate_id:value['candidate_id']=args.candidate_id
            if args.expected_candidate_digest:value['expected_candidate_digest']=args.expected_candidate_digest
            return client.request("POST","/api/v1/projects",ProjectChange.model_validate(value).model_dump(mode="json"))
        require(uuid,"VALIDATION_ERROR","Supply --ledger-uuid or a matching --binding.")
        value=ProjectState(enabled=a=="enable",expected_catalog_revision=args.expected_catalog_revision,request_id=args.request_id)
        return client.request("POST",path+"/state",value.model_dump(mode="json"),uuid)
    require(uuid,"VALIDATION_ERROR","Supply --ledger-uuid or a matching --binding.")
    if g=='decision' and a=='get' and args.source_id:
        require(args.source_namespace and not args.key,'VALIDATION_ERROR','Source lookup needs namespace/ID and no native key.')
        return client.request('GET',path+'/decisions?'+urlencode({'source_namespace':args.source_namespace,'source_id':args.source_id}),uuid=uuid)
    if args.origin=='legacy':
        prefix=path+'/legacy'
        if args.legacy_kind:
            require(g=='query' and a=='context','VALIDATION_ERROR','Legacy collections use query context.')
            from .legacy import FAMILIES
            require(args.legacy_kind in FAMILIES,'VALIDATION_ERROR','Unknown legacy collection.')
            params={k:v for k,v in {'key':args.key,'cursor':args.cursor,'limit':args.limit}.items() if v is not None}
            return client.request('GET',prefix+'/records/'+args.legacy_kind+'?'+urlencode(params),uuid=uuid)
        if args.key:prefix=path+'/decisions/'+args.key+'/legacy'
        params={k:v for k,v in {'version_id':args.source_version,'cursor':args.cursor,'limit':args.limit,'source_id':args.source_id}.items() if v is not None}
        if g=='decision' and a=='as-of':
            require(args.key and args.source_version,'VALIDATION_ERROR','Supply native key and source version.')
            endpoint=prefix+'/as-of';params={'version_id':args.source_version}
        elif (g=='data' and a=='export' or g=='decision' and a=='field') and args.payload:
            endpoint=prefix+('/payload/' if args.key else '/payloads/')+args.payload;params={'offset':args.offset,'limit':args.limit}
        else:
            require(g=='query' and a=='context' or g=='decision' and a=='history','VALIDATION_ERROR','Legacy origin supports context/history/as-of and payload retrieval.')
            endpoint=prefix+('/relations' if args.relations else '' if args.key else '/members')
        return client.request('GET',endpoint+'?'+urlencode(params),uuid=uuid)
    query={k:getattr(args,k) for k in ("q","status","work","owner","cursor","limit") if getattr(args,k) is not None}
    if (g=="decision" and a=="list") or (g=="query" and a in ("search","deprecated")):
        if a=="deprecated":query["status"]="deprecated"
        return client.request("GET",path+"/decisions?"+urlencode(query),uuid=uuid)
    if g=="data":
        if a in ('upgrade-check','upgrade'):
            if a=='upgrade':
                from .approval_api import Upgrade
                data=Upgrade.model_validate({'expected_revision':args.expected_revision if args.expected_revision is not None else data.get('expected_revision'),'request_id':args.request_id or data.get('request_id')}).model_dump(mode='json')
            return client.request('POST',path+'/schema-upgrade'+('/check' if a=='upgrade-check' else ''),data,uuid)
        if a=="artifact-list":
            filters={k:v for k,v in query.items() if k in ('cursor','limit')}
            for key in ('kind','order'):
                if getattr(args,key,None) is not None:filters[key]=getattr(args,key)
            return client.request("GET",path+"/artifacts?"+urlencode(filters),uuid=uuid)
        if a=="artifact-download":
            require(args.artifact_id and args.output,"VALIDATION_ERROR","Artifact download requires --artifact-id and --output.")
            return client.request("GET",path+"/artifacts/"+args.artifact_id+"/content",uuid=uuid,download=args.output)
        routes={"export":"exports","backup":"backups","verify":"verify","restore-check":"restore-check"}
        if a=="restore-check":data={"artifact_id":args.artifact_id or data.get("artifact_id")}
        return client.request("POST",path+"/"+routes[a],data,uuid)
    if g=="change":
        value=Change.model_validate({**data,"validate_only":args.dry_run or data.get("validate_only",False)})
        require(str(value.expected_ledger_uuid)==uuid,"LEDGER_IDENTITY_MISMATCH","Input UUID differs from binding.",409)
        return client.request("POST",path+"/changes",value.model_dump(mode="json"),uuid)
    read=(g=="decision" and a in ("get","history","as-of","field","planning-links","applications")) or (g=="query" and a in ("context","impact")) or a=="list"
    if read:
        require(args.key,"VALIDATION_ERROR","Supply --key.")
        endpoint=path+"/decisions/"+args.key
        params={}
        if a=="list":endpoint+="/"+{"option":"options","reference":"references","link":"links"}[g];params={"limit":args.limit}
        elif a!="get":endpoint+="/"+("fields/"+(args.field or "") if a=="field" else a)
        if a in ('history','planning-links','applications'):params["limit"]=args.limit
        if args.cursor:params["cursor"]=args.cursor
        if a in ("as-of","field"):
            require(args.revision is not None,"VALIDATION_ERROR","Supply --revision.")
            params["revision"]=args.revision
        if a=="field":params.update(offset=args.offset,limit=args.limit)
        return client.request("GET",endpoint+("?"+urlencode(params) if params else ""),uuid=uuid)
    fields=("title","question","answer","rationale","owner_role","baseline","work_tag","resume_trigger",
            "kind","replacement_key","target_key","type","impact","baseline_disposition","selected_option")
    if g=='decision' and a in ('link','apply'):fields=('planning_document','planning_section','expected_document_sha256','expected_projection_sha256','expected_policy_revision','expected_resolution_id')
    opdata={**data,**{k:getattr(args,k) for k in fields if getattr(args,k) is not None}}
    expected=read_input(args.expected_decision_revisions) if args.expected_decision_revisions else {}
    if args.key and args.record_revision is not None:expected[args.key]=args.record_revision
    operation={"op":g+"."+a,"key":args.key,"id":args.id,"data":opdata}
    value=Change(expected_ledger_uuid=uuid,expected_revision=args.expected_revision,
                 expected_decision_revisions=expected,request_id=args.request_id,reason=args.reason,
                 authority_refs=args.authority_ref,operations=[operation],validate_only=args.dry_run)
    return client.request("POST",path+"/changes",value.model_dump(mode="json"),uuid)

def exit_code(value):
    if value.get("ok"):return 0
    code=value.get("error",{}).get("code")
    if code in ("UNAUTHORIZED","FORBIDDEN","SETUP_REQUIRED"):return 4
    if code in ('PROPOSAL_CHANGED','UPGRADE_REQUIRED','ALREADY_UPGRADED','POLICY_CHANGED','DOCUMENT_CHANGED','RESOLUTION_CHANGED','ALREADY_LINKED','ALREADY_RECORDED','ALREADY_APPLIED'):return 3
    if code in ("SERVICE_UNAVAILABLE","RETRY_LATER","DATABASE_UNAVAILABLE","SERVICE_STOPPING","PORT_CONFLICT"):return 5
    if code in ("STALE_REVISION","REVISION_CONFLICT","LEDGER_IDENTITY_MISMATCH","REQUEST_ID_REUSED","CURSOR_STALE","RELATION_CYCLE","DUPLICATE_LEDGER","PROJECT_DISABLED","LOCKED_BASELINE","SERVICE_BUSY","AUTH_STATE_CONFLICT"):return 3
    return 1 if code=="INTERNAL_ERROR" else 2

def main(argv=None):
    args=parser().parse_args(argv)
    try:value=execute(args)
    except Fault as exc:value={"ok":False,"error":{"code":exc.code,"message":exc.message,"details":exc.details,"recovery":exc.recovery}}
    except Exception as exc:
        from pydantic import ValidationError
        if isinstance(exc,(ValidationError,ValueError,TypeError,OSError)):
            value={"ok":False,"error":{"code":"VALIDATION_ERROR","message":"Check required arguments and input file shape.","recovery":"Use command --help; keep the original request ID for retries."}}
        else:raise
    if args.json:print(encode(value))
    elif value.get("ok"):
        print("Status: success")
        print(json.dumps(value.get("data",value),indent=2,ensure_ascii=False))
    else:
        err=value["error"];print("Status: no-go\nReason: "+err["message"]+"\nNext action: "+err.get("recovery","Inspect command help."),file=sys.stderr)
    return exit_code(value)

if __name__=="__main__":
    raise SystemExit(main())
