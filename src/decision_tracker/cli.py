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
           "defer","resume","challenge","resolve-challenge","set-work","history","as-of","field"]

def common(parser,suppress=True):
    default=argparse.SUPPRESS if suppress else None
    for name in ["base-url","config","project","ledger-uuid","token-env","input","request-id","reason",
                 "expected-decision-revisions","binding","deployment","credential-principal","principal","token-id"]:
        parser.add_argument("--"+name,default=default)
    for name in ["expected-revision","expected-catalog-revision","record-revision"]:
        parser.add_argument("--"+name,type=int,default=default)
    parser.add_argument("--json",action="store_true",default=argparse.SUPPRESS if suppress else False)
    parser.add_argument("--dry-run",action="store_true",default=argparse.SUPPRESS if suppress else False)
    parser.add_argument("--authority-ref",action="append",default=argparse.SUPPRESS if suppress else [])
    for name in ["key","id","name","relative-path","title","question","answer","rationale","owner-role","baseline",
                 "work-tag","resume-trigger","kind","replacement-key","target-key","type","impact","baseline-disposition",
                 "selected-option","cursor","q","status","work","owner","artifact-id","output","bind","candidate-id","expected-candidate-digest"]:
        parser.add_argument("--"+name,default=default)
    parser.add_argument("--prompt-code",action="store_true",default=argparse.SUPPRESS if suppress else False)
    parser.add_argument("--store-local",action="store_true",default=argparse.SUPPRESS if suppress else False)
    parser.add_argument("--limit",type=int,default=argparse.SUPPRESS if suppress else 50)
    parser.add_argument("--port",type=int,default=default)
    parser.add_argument("--data-root",default=default)
    parser.add_argument("--revision",type=int,default=default)
    parser.add_argument("--offset",type=int,default=argparse.SUPPRESS if suppress else 0)
    parser.add_argument("--field",default=default)

def parser():
    root=argparse.ArgumentParser(prog="decision-tracker",description=__doc__,
        epilog="Use --input FILE (or - for stdin) for structured fields. Mutations require explicit revision, request ID and reason. Agent credentials use an explicit environment variable or protected local principal.")
    common(root,False)
    groups=root.add_subparsers(dest="group",required=True)
    definitions={
        "service":["serve","status","catalog-backup","ensure-running","open","install-launcher","uninstall-launcher","configure-credentials","stop"],
        "auth":["setup-code","recover","reset-password","migrate","token"],
        "project":["list","show","create","register","disable","enable"],
        "decision":DECISIONS,
        "option":["add","list","edit","retire"],
        "reference":["add","list","edit","retire"],
        "link":["add","list","unlink"],
        "query":["search","context","impact","deprecated"],
        "change":["apply"],
        "data":["export","import-validate","import-new","candidates","prepare-candidate","backup","verify","restore-check","artifact-list","artifact-download","upgrade-check","upgrade"]}
    for group,verbs in definitions.items():
        parent=groups.add_parser(group,help=group+" operations")
        children=parent.add_subparsers(dest="action",required=True)
        for verb in verbs:
            child=children.add_parser(verb,description=f"{group} {verb}; use the shared versioned API.")
            common(child)
            if group=='auth' and verb=='token':
                token_actions=child.add_subparsers(dest='token_action',required=True)
                for action in ('create','rotate','revoke','list'):common(token_actions.add_parser(action))
    return root

def read_input(path):
    if not path:return {}
    if path!="-":require(Path(path).stat().st_size<=10*1024*1024,"LIMIT_EXCEEDED","Input exceeds10MiB.",413)
    raw=sys.stdin.read(10*1024*1024+1) if path=="-" else Path(path).read_text(encoding="utf-8")
    require(len(raw.encode())<=10*1024*1024,"LIMIT_EXCEEDED","Input exceeds10MiB.",413)
    try:value=json.loads(raw)
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
            cap=20*1024*1024 if download else 65536
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
    is_change=args.group=="change" or (args.group in ("decision","option","reference","link") and args.action not in ("list","get","history","as-of","field"))
    require(not args.dry_run or is_change,"VALIDATION_ERROR","Dry-run is supported only for decision change operations.")
    if args.group=='auth' or args.group=='service' and args.action in ('ensure-running','open','install-launcher','uninstall-launcher','configure-credentials','stop'):
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
    require(args.project is not None,"VALIDATION_ERROR","Supply --project.")
    import re
    require(re.fullmatch(r"[a-z][a-z0-9-]{0,47}",args.project) is not None,"VALIDATION_ERROR","Invalid project ID.")
    path="/api/v1/projects/"+args.project
    if g=="project":
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
            return client.request("GET",path+"/artifacts?"+urlencode({k:v for k,v in query.items() if k in ("cursor","limit")}),uuid=uuid)
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
    read=(g=="decision" and a in ("get","history","as-of","field")) or (g=="query" and a in ("context","impact")) or a=="list"
    if read:
        require(args.key,"VALIDATION_ERROR","Supply --key.")
        endpoint=path+"/decisions/"+args.key
        params={}
        if a=="list":endpoint+="/"+{"option":"options","reference":"references","link":"links"}[g];params={"limit":args.limit}
        elif a!="get":endpoint+="/"+("fields/"+(args.field or "") if a=="field" else a)
        if a=="history":params["limit"]=args.limit
        if args.cursor:params["cursor"]=args.cursor
        if a in ("as-of","field"):
            require(args.revision is not None,"VALIDATION_ERROR","Supply --revision.")
            params["revision"]=args.revision
        if a=="field":params.update(offset=args.offset,limit=args.limit)
        return client.request("GET",endpoint+("?"+urlencode(params) if params else ""),uuid=uuid)
    fields=("title","question","answer","rationale","owner_role","baseline","work_tag","resume_trigger",
            "kind","replacement_key","target_key","type","impact","baseline_disposition","selected_option")
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
    if code in ('PROPOSAL_CHANGED','UPGRADE_REQUIRED','ALREADY_UPGRADED'):return 3
    if code in ("SERVICE_UNAVAILABLE","RETRY_LATER","DATABASE_UNAVAILABLE","SERVICE_STOPPING","PORT_CONFLICT"):return 5
    if code in ("STALE_REVISION","LEDGER_IDENTITY_MISMATCH","REQUEST_ID_REUSED","CURSOR_STALE","RELATION_CYCLE","DUPLICATE_LEDGER","PROJECT_DISABLED","LOCKED_BASELINE","SERVICE_BUSY","AUTH_STATE_CONFLICT"):return 3
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
