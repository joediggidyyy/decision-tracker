"""Typed approval evidence, distinct from immutable recording time."""
from datetime import datetime, date, timezone, timedelta
from typing import Literal
from uuid import uuid4
from pydantic import Field, model_validator
from .models import Model, ReferenceText
from .errors import require
from . import store

class Approval(Model):
    mode: Literal['authenticated_now','reported']
    precision: Literal['exact','date','unknown'] | None = None
    approver: str | None = Field(default=None,min_length=1,max_length=160)
    sources: list[ReferenceText] = Field(default_factory=list,max_length=32)
    occurred_at: datetime | None = None
    occurred_date: date | None = None
    utc_offset_minutes: int | None = Field(default=None,ge=-720,le=840)
    timezone_label: str | None = Field(default=None,max_length=80)

    @model_validator(mode='after')
    def shape(self):
        if self.mode=='authenticated_now':
            if self.model_fields_set != {'mode'}:raise ValueError('Current approval accepts only mode; the server records identity and time.')
            return self
        if not self.approver or not self.approver.strip() or not self.sources or any(not x.strip() for x in self.sources):
            raise ValueError('Enter who approved and the message, document or note recording approval.')
        if self.precision=='unknown':
            if any(x is not None for x in (self.occurred_at,self.occurred_date,self.utc_offset_minutes,self.timezone_label)):
                raise ValueError('Unknown date cannot contain date or timezone values.')
        elif self.precision in ('exact','date'):
            if self.utc_offset_minutes is None or self.utc_offset_minutes%15:raise ValueError('Choose a valid UTC offset.')
            if self.precision=='date':
                if self.occurred_date is None or self.occurred_at is not None:raise ValueError('Supply a date without a time.')
            elif self.occurred_at is None or self.occurred_at.utcoffset() is None or self.occurred_date is not None or self.occurred_at.utcoffset()!=timedelta(minutes=self.utc_offset_minutes):
                raise ValueError('Supply an exact time with its matching UTC offset.')
        else:raise ValueError('Choose date and time known, date only, or date unknown.')
        return self

def normalized(text):return (text or '').replace('\r\n','\n').strip()

def prepare(db, principal, request, stamp):
    """Return operation-local evidence without changing the hashed request."""
    events={}; operations=[op for op in request.operations if op.op in ('decision.close','decision.edit-resolution')]
    for ordinal,op in enumerate(request.operations):
        if op not in operations:continue
        key=op.key
        require(key and not key.startswith('@'),'VALIDATION_ERROR','Record approval for an existing decision.')
        require(sum(x.key==key for x in request.operations)==1,'VALIDATION_ERROR','Save this decision separately from other changes to it.')
        obj=store.get(db,'decisions',key); data=op.data;raw=data.get('approval'); structured=raw is not None
        if structured and isinstance(raw,dict) and raw.get('mode')=='reported':
            require(isinstance(raw.get('approver'),str) and raw['approver'].strip(),'APPROVER_REQUIRED','Enter who approved this decision.',fields=[{'field':f'/operations/{ordinal}/data/approval/approver'}])
            require(isinstance(raw.get('sources'),list) and raw['sources'] and all(isinstance(x,str) and x.strip() for x in raw['sources']),'APPROVAL_SOURCE_REQUIRED','Add the message, document or note that records the approval.',fields=[{'field':f'/operations/{ordinal}/data/approval/sources'}])
        from pydantic import ValidationError
        from .errors import Fault
        try:approval=Approval.model_validate(raw) if structured else None
        except ValidationError as exc:
            raise Fault('APPROVAL_DATE_INVALID','Choose valid approval details, or select Date unknown.',details={'fields':[{'field':f'/operations/{ordinal}/data/approval/'+('/'.join(map(str,x['loc'])) or 'precision'),'message':x['msg']} for x in exc.errors()]}) from None
        require(not structured or request.occurred_at is None,'VALIDATION_ERROR','Use the approval date, not a second transaction date.')
        event_id=str(uuid4());ref='dt-approval:'+event_id
        event={'schema_version':'decision-tracker.approval/v1','event_id':event_id,'decision_key':key,
               'ledger_revision':request.expected_revision+1,'operation_ordinal':ordinal,
               'supersedes_event_id':None,'kind':'close' if op.op=='decision.close' else 'edit_resolution',
               'mode':approval.mode if approval else 'legacy_reference','recorded_by':principal.id,
               'auth_method':principal.auth_method,'recorded_at':stamp,'reported_approver':None,
               'precision':'unknown','occurred_at':None,'occurred_date':None,'utc_offset_minutes':None,
               'timezone_label':None,'sources':list(request.authority_refs),'selected_option':None,
               'answer':data.get('answer',obj['answer']),'rationale':data.get('rationale',obj['rationale'])}
        previous=db.execute('SELECT event_id FROM approval_events WHERE decision_key=? ORDER BY ledger_revision DESC,operation_ordinal DESC LIMIT 1',(key,)).fetchone()
        if previous:event['supersedes_event_id']=previous[0]
        if approval:
            if approval.mode=='authenticated_now':
                require(principal.auth_method=='human_password_session','FORBIDDEN','Only a signed-in person can approve now.',403)
                event.update(precision='exact',occurred_at=stamp,utc_offset_minutes=0,timezone_label='UTC',sources=[ref])
            else:
                current=datetime.fromisoformat(stamp.replace('Z','+00:00'))
                if approval.precision=='exact':
                    require(approval.occurred_at<=current,'APPROVAL_DATE_FUTURE','The approval time cannot be in the future.')
                if approval.precision=='date':
                    require(approval.occurred_date<=current.astimezone(timezone(timedelta(minutes=approval.utc_offset_minutes))).date(),'APPROVAL_DATE_FUTURE','The approval date cannot be in the future.')
                event.update(reported_approver=approval.approver.strip(),precision=approval.precision,
                             occurred_at=approval.occurred_at.astimezone(timezone.utc).isoformat() if approval.occurred_at else None,
                             occurred_date=approval.occurred_date.isoformat() if approval.occurred_date else None,
                             utc_offset_minutes=approval.utc_offset_minutes,timezone_label=approval.timezone_label,
                             sources=[x.strip() for x in approval.sources]+[ref])
        selected=data.get('selected_option')
        if 'selected_option' not in data and op.op=='decision.edit-resolution':
            row=db.execute("SELECT id FROM alternatives WHERE decision_key=? AND disposition='selected'",(key,)).fetchone();selected=row[0] if row else None
        if selected:
            option=store.get(db,'alternatives',selected)
            require(option['decision_key']==key and option['disposition'] not in ('retired','rejected'),'INVALID_TRANSITION','Choose a current proposal. Reconsider a rejected proposal before selecting it.')
            if structured:
                require(type(data.get('expected_option_revision')) is int and data['expected_option_revision']==option['revision'],'PROPOSAL_CHANGED','This proposal changed. Review the latest version before saving.',409)
                exact=normalized(event['answer'])==normalized(option['description'] if option['description'].strip() else option['title'])
                unchanged=op.op=='decision.edit-resolution' and option['disposition']=='selected' and event['answer']==obj['answer']
                require(exact or unchanged,'ANSWER_PROPOSAL_MISMATCH','Your answer differs from the proposal. Save it as a written answer or restore the proposal text.')
            event['selected_option']={k:option[k] for k in ('id','revision','title','description','benefit','cost')}
        elif 'expected_option_revision' in data:
            require(False,'VALIDATION_ERROR','Proposal revision requires a selected proposal.')
        require(len(store.encode(event).encode())<=128*1024,'LIMIT_EXCEEDED','Approval exceeds the record size limit.',413)
        events[ordinal]=event
    return events

def insert(db,event):
    db.execute('INSERT INTO approval_events VALUES(?,?,?,?,?,?,?)',(event['event_id'],event['decision_key'],event['ledger_revision'],event['operation_ordinal'],event['supersedes_event_id'],store.encode(event),store.digest(event)))

def summary(event):
    return {k:event[k] for k in ('event_id','mode','recorded_by','reported_approver','recorded_at','precision','occurred_at','occurred_date','utc_offset_minutes','ledger_revision')}

def latest(db,key,revision):
    if store.metadata(db)['schema_version']==1:return None
    row=db.execute('SELECT event_json FROM approval_events WHERE decision_key=? AND ledger_revision<=? ORDER BY ledger_revision DESC,operation_ordinal DESC LIMIT 1',(key,revision)).fetchone()
    return summary(__import__('json').loads(row[0])) if row else None
