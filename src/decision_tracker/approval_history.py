"""Validate persisted approval evidence against immutable transaction snapshots."""
import json
from datetime import datetime, timezone, timedelta
from uuid import UUID
from . import store
from .errors import require

def validate(db,meta):
    def check(ok):require(ok,'INTEGRITY_FAILED','Approval history is inconsistent.',409)
    receipts=[store.unpack(x) for x in db.execute('SELECT * FROM schema_upgrades')]
    check(len(receipts)==1)
    receipt=receipts[0];boundary=receipt['ledger_revision']
    check(receipt['to_version']==2 and receipt['from_version'] in (0,1) and 0<=boundary<=meta['ledger_revision'])
    if receipt['from_version']==0:
        check(boundary==0 and receipt['receipt_json']=={'initialized':True,'ledger_uuid':meta['ledger_uuid'],'schema_version':2,'revision':0})
        check(receipt['request_hash']==store.digest(receipt['receipt_json']))
    else:
        body={'expected_revision':boundary,'request_id':receipt['request_id']}
        check(receipt['request_hash']==store.digest(body) and bool(receipt['backup_artifact_id']))
        check(receipt['receipt_json'].get('ledger_uuid')==meta['ledger_uuid'] and receipt['receipt_json'].get('revision')==boundary)
    events={};last={}
    for row in db.execute('SELECT * FROM approval_events ORDER BY ledger_revision,operation_ordinal'):
        e=json.loads(row['event_json']);check(store.digest(e)==row['event_sha256'])
        UUID(e['event_id'])
        check(set(e)=={'schema_version','event_id','decision_key','ledger_revision','operation_ordinal','supersedes_event_id','kind','mode','recorded_by','auth_method','recorded_at','reported_approver','precision','occurred_at','occurred_date','utc_offset_minutes','timezone_label','sources','selected_option','answer','rationale'})
        check(e['schema_version']=='decision-tracker.approval/v1')
        check(e['auth_method'] in ('human_password_session','agent_bearer','legacy_token_session'))
        check(len(store.encode(e).encode())<=131072)
        check(all(e[k]==row[k] for k in ('event_id','decision_key','ledger_revision','operation_ordinal','supersedes_event_id')))
        check(e['ledger_revision']>boundary and e['supersedes_event_id']==last.get(e['decision_key']))
        tx=db.execute('SELECT * FROM transactions WHERE ledger_revision=?',(e['ledger_revision'],)).fetchone();check(tx is not None)
        check(e['recorded_by']==tx['principal_id'] and e['recorded_at']==tx['recorded_at'])
        request=json.loads(tx['request_json']);ops=request['operations'];check(0<=e['operation_ordinal']<len(ops))
        op=ops[e['operation_ordinal']];check(op['op'] in ('decision.close','decision.edit-resolution') and op['key']==e['decision_key'])
        check(e['kind']==('close' if op['op']=='decision.close' else 'edit_resolution'))
        snaprow=db.execute('SELECT snapshot_json FROM revisions WHERE decision_key=? AND ledger_revision=?',(e['decision_key'],e['ledger_revision'])).fetchone();check(snaprow is not None)
        snap=json.loads(snaprow[0]);check(snap['answer']==e['answer'] and snap['rationale']==e['rationale'] and snap['authority_refs']==e['sources'])
        approval=op['data'].get('approval');ref='dt-approval:'+e['event_id']
        if approval is None:
            check(e['mode']=='legacy_reference' and e['precision']=='unknown' and e['sources']==request['authority_refs'])
            check(all(e[k] is None for k in ('reported_approver','occurred_at','occurred_date','utc_offset_minutes','timezone_label')))
        else:
            from .approvals import Approval
            a=Approval.model_validate(approval);check(e['mode']==a.mode)
            if a.mode=='authenticated_now':
                check(e['auth_method']=='human_password_session' and e['occurred_at']==e['recorded_at'] and e['precision']=='exact' and e['sources']==[ref])
                check(e['reported_approver'] is None and e['occurred_date'] is None and e['utc_offset_minutes']==0 and e['timezone_label']=='UTC')
            else:
                check(e['reported_approver']==a.approver.strip() and e['precision']==a.precision and e['sources']==[x.strip() for x in a.sources]+[ref])
                check(e['occurred_date']==(a.occurred_date.isoformat() if a.occurred_date else None) and e['utc_offset_minutes']==a.utc_offset_minutes)
                check((datetime.fromisoformat(e['occurred_at'])==a.occurred_at) if a.occurred_at else e['occurred_at'] is None)
                check(e['timezone_label']==a.timezone_label)
                recorded=datetime.fromisoformat(e['recorded_at'])
                if a.occurred_at:check(a.occurred_at<=recorded)
                if a.occurred_date:check(a.occurred_date<=recorded.astimezone(timezone(timedelta(minutes=a.utc_offset_minutes))).date())
        check(e['answer']==op['data'].get('answer',e['answer']) and e['rationale']==op['data'].get('rationale',e['rationale']))
        selected=e['selected_option']
        if selected:
            prior=db.execute('SELECT snapshot_json FROM revisions WHERE decision_key=? AND ledger_revision<? ORDER BY ledger_revision DESC LIMIT 1',(e['decision_key'],e['ledger_revision'])).fetchone();check(prior is not None)
            old=next((x for x in json.loads(prior[0])['alternatives'] if x['id']==selected['id']),None);check(old is not None)
            check(selected=={k:old[k] for k in ('id','revision','title','description','benefit','cost')})
            check(any(x['id']==selected['id'] and x['disposition']=='selected' for x in snap['alternatives']))
            check(op['data'].get('selected_option',selected['id'])==selected['id'])
        else:check(not any(x['disposition']=='selected' for x in snap['alternatives']))
        events[(e['ledger_revision'],e['operation_ordinal'])]=e;last[e['decision_key']]=e['event_id']
    for tx in db.execute('SELECT * FROM transactions WHERE ledger_revision>?',(boundary,)):
        for ordinal,op in enumerate(json.loads(tx['request_json'])['operations']):
            if op['op'] in ('decision.close','decision.edit-resolution'):check((tx['ledger_revision'],ordinal) in events)
