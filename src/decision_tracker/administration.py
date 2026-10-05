"""Enumerated OS-owner operations; not exposed over HTTP."""
from pathlib import Path
import json,hashlib
from .errors import require,Fault
from .windows_local import read_bundle,save_bundle

def recover_token_journal(value,store):
    journal=Path(value['path']).parent/'token-journal.json'
    if not journal.exists():return
    item=json.loads(journal.read_text());bundle=read_bundle(Path(value['bundle']));raw=bundle.get('tokens',{}).get(item['principal'])
    published=raw and hashlib.sha256(raw.encode()).hexdigest()==item['digest']
    with store.db() as db:
        if published:
            db.execute("UPDATE tokens SET state='active' WHERE id=? AND state='pending'",(item['new_id'],))
            if item['old_id']:db.execute("UPDATE tokens SET state='revoked',revoked=? WHERE id=?",(store.now(db),item['old_id']))
        else:db.execute("UPDATE tokens SET state='revoked',revoked=? WHERE id=? AND state='pending'",(store.now(db),item['new_id']))
    journal.replace(journal.with_name('token-journal-completed.json'))

def dispatch(value,cfg,store,life,operation,args):
    allowed={'setup-code':{'supplied'},'recover':set(),'reset-password':{'code','password','confirmation'},'token-create':{'principal','store_local'},'token-rotate':{'token_id','store_local'},'token-revoke':{'token_id'},'token-list':set(),'status':set(),'stop':set()}
    require(operation in allowed and set(args)<=allowed[operation],'VALIDATION_ERROR','Unknown local operation or field.')
    if operation=='status':return life.status() if life else {'state':'STOPPED'}
    if operation=='stop':
        if life:life.stop(explicit=True)
        return {'state':'DRAINING' if life else 'STOPPED'}
    if life:life.enter()
    try:
        if operation=='setup-code':return {'code':store.issue('bootstrap',args.get('supplied')),'expires_in_seconds':900}
        if operation=='recover':return {'code':store.issue('recovery'),'expires_in_seconds':900}
        if operation=='reset-password':store.redeem('recovery',args['code'],args['password'],args['confirmation']);return {'password_reset':True}
        recover_token_journal(value,store)
        if operation=='token-list':return {'tokens':store.token_list()}
        if operation=='token-revoke':store.token_revoke(args['token_id']);return {'revoked':True}
        old=None;principal=args.get('principal')
        if operation=='token-rotate':
            old=next((r for r in store.token_list() if r['id']==args['token_id'] and r['state']=='active'),None)
            require(old,'NOT_FOUND','Active token unavailable.',404);principal=old['principal']
        require(principal!='operator' and principal in {p.id for p in cfg.principals},'FORBIDDEN','Select an explicitly configured agent principal.',403)
        stored=bool(args.get('store_local'));key,raw=store.token_create(principal,state='pending')
        if stored:
            from .deployment import atomic_json
            bundle=read_bundle(Path(value['bundle']));bundle.setdefault('tokens',{})[principal]=raw
            journal=Path(value['path']).parent/'token-journal.json'
            atomic_json(journal,{'new_id':key,'old_id':old['id'] if old else None,'principal':principal,'digest':hashlib.sha256(raw.encode()).hexdigest()})
            save_bundle(Path(value['bundle']),bundle);recover_token_journal(value,store)
        else:
            with store.db() as db:
                db.execute("UPDATE tokens SET state='active' WHERE id=?",(key,))
                if old:db.execute("UPDATE tokens SET state='revoked',revoked=? WHERE id=?",(store.now(db),old['id']))
        return {'token_id':key,'token':raw,'principal':principal,'stored_locally':stored}
    except (KeyError,TypeError):raise Fault('VALIDATION_ERROR','Local operation fields are invalid.') from None
    finally:
        if life:life.leave()
