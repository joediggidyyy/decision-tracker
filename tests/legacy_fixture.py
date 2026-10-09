"""Synthetic source-only fixtures; no owner or business data is mounted."""
from uuid import uuid4
from decision_tracker import legacy

def request(statuses=('closed','open','locked','deprecated'),extra_members=0,payload_text=None,source_title=None):
    value={'format':'decision-tracker.legacy-import/v1','namespace':'legacy-test','contract_sha256':legacy.contract_digest(),
           'source_manifest_sha256':'a'*64,'target_ledger_uuid':str(uuid4()),'request_id':str(uuid4()),
           **{name:[] for name in ('identities','versions','payloads','members','associations','relations','projections','anchors','absences','appearances','native_seeds')}}
    locator='planning/source.json';filehash='b'*64;vid=legacy.digest(['legacy-version/v1',value['namespace'],locator,filehash])
    value['versions']=[{'version_id':vid,'namespace':value['namespace'],'locator':locator,'file_sha256':filehash,'source_kind':'json','source_order':0,'source_revisions':['snapshot-1'],'parent_commit_ids':[],'provenance_member_ids':[]}]
    value['appearances']=[{'namespace':value['namespace'],'locator':locator,'source_revision':'snapshot-1','version_id':vid,'file_presence':'present','source_order':0},
        {'namespace':value['namespace'],'locator':'planning/absent.json','source_revision':'snapshot-1','version_id':None,'file_presence':'absent','source_order':1}]
    payloads={}
    for i,status in enumerate(statuses,1):
        key='D%06d'%i;sid='SOURCE-'+str(i)
        fields={'title':'Source '+sid,'question':None,'answer':None,'rationale':None,'status':'closed' if status=='locked' else status,
                'locked':status=='locked','work_tag':None,'authority_refs':[]}
        if status=='locked':fields['baseline']='source-baseline'
        if source_title is not None:fields['title']=source_title
        if status=='deprecated':fields.update(deprecation_kind=None,deprecation_reason=None)
        source={**fields,'literal':legacy.parse('{"decimal":1.2300,"negative_zero":-0,"exp":1E+02,"null":null,"empty":"","ordered":[2,1],"unicode":"🧭"}'),
                'events':[{'event_id':'EVT-2','time':None},{'event_id':'EVT-1','time':None}]}
        if payload_text is not None:source['content']=payload_text
        ph=legacy.digest(source);raw=legacy.e1(source)
        payloads[ph]={'payload_sha256':ph,'literal_type':'object','value_json':raw,'encoded_bytes':len(raw.encode())}
        selector='/decisions/'+str(i-1);mid=legacy.digest(['legacy-member/v1',vid,selector])
        value['members'].append({'member_id':mid,'version_id':vid,'selector':selector,'subject_kind':'decision','source_id':sid,'source_order':i,'payload_sha256':ph})
        value['identities'].append({'namespace':value['namespace'],'source_id':sid,'native_key':key,'aliases':['OLD-'+str(i)]})
        value['associations'].append({'member_id':mid,'namespace':value['namespace'],'source_id':sid,'association_kind':'direct-decision'})
        value['anchors'].append({'native_key':key,'member_id':mid,'original_locator':locator,'file_sha256':filehash,'selector':selector,'incorporation_state':'reference-only','source_resolution_identity':None})
        projection=[]
        for field,data in sorted(fields.items()):
            unknown=data is None or field=='authority_refs'
            p={'native_key':key,'field':field,'origin_member_id':mid,'selector':'/'+field,
               'projection_kind':'none' if unknown else 'exact','known_state':'explicit_source_unknown' if unknown else 'exact_source',
               'projection_json':legacy.e1(data),'projection_sha256':legacy.digest(data)}
            projection.append(p);value['projections'].append(p)
        value['native_seeds'].append({'native_key':key,'origin_source_id':sid,'projection_fields':projection})
    for i in range(extra_members):
        raw=legacy.e1({'context':i});ph=legacy.digest({'context':i});selector='/context/'+str(i);mid=legacy.digest(['legacy-member/v1',vid,selector])
        payloads[ph]={'payload_sha256':ph,'literal_type':'object','value_json':raw,'encoded_bytes':len(raw.encode())}
        value['members'].append({'member_id':mid,'version_id':vid,'selector':selector,'subject_kind':'disposition','source_id':None,'source_order':100+i,'payload_sha256':ph})
    # Typed nondecision context stays project-visible; no native endpoint is fabricated.
    first=value['members'][0]
    endpoint={'kind':'decision','namespace':value['namespace'],'source_id':'SOURCE-1','literal_member_id':first['member_id'],'literal_pointer':''}
    target={'kind':'evidence','namespace':value['namespace'],'source_id':'EVIDENCE-1','literal_member_id':None,'literal_pointer':''}
    relation={'version_id':vid,'member_id':first['member_id'],'source_endpoint':endpoint,'target_endpoint':target,'relation_type':'supported-by','source_order':0,'literal_pointer':'/events'}
    relation['relation_id']=legacy.digest(['legacy-relation/v1',first['member_id'],relation['relation_type'],endpoint,target,0]);value['relations']=[relation]
    absence={'version_id':vid,'selector':'/earlier-missing','presence':'absent','accounting_member_ids':[first['member_id']]}
    absence['absence_id']=legacy.digest(['legacy-absence/v1',vid,absence['selector']]);value['absences']=[absence]
    value['payloads']=list(payloads.values())
    return legacy.canonical_order(value)
