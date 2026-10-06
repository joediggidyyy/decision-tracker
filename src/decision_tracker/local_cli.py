"""Owner-facing credential/setup commands. Secret output is interactive only."""
from pathlib import Path
import getpass,sys,os
from .errors import require
from .deployment import default_path,load,initialize,local_admin,ensure,open_app,install_protocol,uninstall_protocol

def terminal(args,confirmation=None):
    require(sys.stdin.isatty() and sys.stdout.isatty() and not args.json,'INTERACTIVE_REQUIRED','Run this command in a private local terminal without redirection.')
    if confirmation:require(input(confirmation+' Type YES: ')=='YES','CANCELLED','Operation cancelled.')

def execute(args):
    path=Path(args.deployment or default_path())
    if args.group=='project' and args.action=='policy' and args.policy_action=='set':
        from .cli import read_input
        from .applications import PolicyChange
        uuid=args.ledger_uuid
        if args.binding:
            binding=read_input(args.binding)
            require(binding.get('project_id')==args.project,'LEDGER_IDENTITY_MISMATCH','Binding belongs to another project.',409)
            uuid=uuid or binding.get('ledger_uuid')
        require(args.project and uuid,'VALIDATION_ERROR','Supply --project and an explicit ledger binding.')
        data=read_input(args.input)
        for field in ('expected_policy_revision','request_id','reason','anchor_required','planning_roots'):
            v=getattr(args,field,None)
            if v is not None:data[field]=v
        if isinstance(data.get('anchor_required'),str):data['anchor_required']=data['anchor_required']=='true'
        request=PolicyChange.model_validate(data).model_dump(mode='json')
        return local_admin(path,'project-policy-set',project_id=args.project,ledger_uuid=uuid,request=request)
    if args.group=='service':
        if args.action=='install-launcher':
            if not path.exists():initialize(path)
            return {'ok':True,'data':install_protocol(path)}
        if args.action=='uninstall-launcher':return {'ok':True,'data':uninstall_protocol(path)}
        if args.action=='ensure-running':return {'ok':True,'data':ensure(path)}
        if args.action=='open':return {'ok':True,'data':open_app(path)}
        if args.action=='stop':return {'ok':True,'data':local_admin(path,'stop')}
        if args.action=='configure-credentials':
            args.action='setup-code';args.group='auth'
    action=args.action
    if action=='migrate':
        terminal(args,'Disable legacy operator-token browser login and create the password credential store?')
        require(args.config and not path.exists(),'SETUP_REQUIRED','Supply an existing config and a new deployment path.')
        from .config import load_config
        from .api import InstanceLock
        from .credentials import Credentials
        from .deployment import atomic_json
        cfg=load_config(args.config)
        require(not cfg.auth_store,'ALREADY_EXISTS','This configuration already uses password authentication.',409)
        imports=[]
        for principal in cfg.principals:
            if principal.id=='operator':continue
            raw=os.environ.get(principal.token_env)
            require(raw and len(raw)>=32 and not raw.startswith('synthetic-'),'SETUP_REQUIRED','Provide each existing agent credential privately before migration.')
            imports.append((principal.id,raw))
        require(len({raw for _,raw in imports})==len(imports),'VALIDATION_ERROR','Agent credentials must be distinct.')
        cfg.root.mkdir(parents=True,exist_ok=True)
        lock=InstanceLock(cfg.root/'.service.lock');lock.acquire()
        try:
            # Publish the usable descriptor only after all agent verifiers exist.
            value=initialize(path,data_root=cfg.data_root,port=cfg.port,publish=False,config=cfg)
            store=Credentials(path.parent/'auth.sqlite')
            for principal,raw in imports:store.token_create(principal,raw)
            atomic_json(path.parent/'legacy-config-backup.json',cfg.model_dump(mode='json'))
            atomic_json(path.parent/'migration-receipt.json',{'legacy_operator_disabled':True,'agent_principals':[p for p,_ in imports]})
            atomic_json(path,value)
        finally:lock.release()
        result=local_admin(path,'setup-code');print('One-time setup code (expires in 15 minutes): '+result.pop('code'))
        return {'ok':True,'data':{'migrated':True}}
    if action=='setup-code':
        terminal(args)
        supplied=getpass.getpass('Temporary setup password: ') if args.prompt_code else None
        result=local_admin(path,'setup-code',supplied=supplied)
        print('One-time setup code (expires in 15 minutes): '+result.pop('code'))
        return {'ok':True,'data':result}
    if action=='recover':
        terminal(args,'Revoke all human sessions and replace password access with CLI recovery? Agent tokens remain active.')
        result=local_admin(path,'recover');print('One-time recovery code (expires in 15 minutes): '+result.pop('code'))
        return {'ok':True,'data':result}
    if action=='reset-password':
        terminal(args)
        return {'ok':True,'data':local_admin(path,'reset-password',code=getpass.getpass('Recovery code: '),password=getpass.getpass('New password: '),confirmation=getpass.getpass('Confirm password: '))}
    if action=='token':
        verb=args.token_action
        if verb=='list':return {'ok':True,'data':local_admin(path,'token-list')}
        terminal(args,'Revoke this agent token?' if verb=='revoke' else None)
        values={'token_id':args.token_id} if verb!='create' else {'principal':args.principal}
        if verb!='revoke':values['store_local']=args.store_local
        result=local_admin(path,'token-'+verb,**values)
        if 'token' in result:print('Agent token (shown once): '+result.pop('token'))
        return {'ok':True,'data':result}
    require(False,'VALIDATION_ERROR','Unknown local command.')
