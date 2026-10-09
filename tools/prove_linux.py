"""Reuse a configured rootless construction backend; no signed release authority."""
from pathlib import Path
import hashlib,io,json,os,subprocess,tarfile,time,uuid

def run(root,args,source_files):
    from prove import sha
    runtime=json.loads(Path(args.runtime_file).read_text(encoding='utf-8'))
    required={'distribution','user','construction_root','image','retention_helper','retention_helper_sha256'}
    if set(runtime)!=required:raise ValueError('Use the exact names-only Linux runtime fields.')
    if not runtime['construction_root'].startswith('/home/') or not runtime['retention_helper'].startswith(runtime['construction_root']+'/'):
        raise ValueError('Use the existing construction root and contained retention helper.')
    if not runtime['image'].startswith('sha256:') or len(runtime['image'])!=71:raise ValueError('Pin the existing image digest.')
    if not 1<=args.budget_seconds<=180:raise ValueError('Linux construction budget must be 1–180 seconds.')
    input_path=Path(args.input_manifest).resolve();supplied=json.loads(input_path.read_text(encoding='utf-8'))
    if set(supplied)!={'files','contract_sha256'}:raise ValueError('Unexpected input manifest fields.')
    selected=[];projects=set()
    for row in supplied['files']:
        if set(row)!={'project','path','sha256','bytes'}:raise ValueError('Unexpected selected input fields.')
        p=Path(row['path']).resolve()
        if not p.is_relative_to(root/'.local') or p.is_symlink() or not p.is_file():raise ValueError('Inputs must be reviewed local copies.')
        if sha(p)!=row['sha256'] or p.stat().st_size!=row['bytes']:raise ValueError('Selected input bytes changed.')
        if row['project'] in projects or not row['project'].replace('-','').isalnum():raise ValueError('Ambiguous namespace.')
        projects.add(row['project']);selected.append((row,p))
    if projects!={'qa-engine','polymath-ledger'} or sum(row['bytes'] for row,p in selected)>10*1024**2:
        raise ValueError('Use the bounded reviewed two-project selection.')
    if supplied['contract_sha256']!=sha(root/'src/decision_tracker/schemas/legacy-import-v1.json'):raise ValueError('Contract changed.')
    attempt=root/'.local/proofs'/uuid.uuid4().hex;copy=attempt/'source';copy.mkdir(parents=True)
    before={p.relative_to(root).as_posix():sha(p) for p in source_files(root) if not p.relative_to(root).as_posix().startswith('.local/')}
    for rel in before:
        dest=copy/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((root/rel).read_bytes())
    files=[]
    for row,p in selected:
        rel='frozen-inputs/'+row['project']+'.json';dest=copy/rel;dest.parent.mkdir(exist_ok=True);dest.write_bytes(p.read_bytes())
        files.append({k:row[k] for k in ('project','sha256','bytes')}|{'copy_path':rel})
    manifest={'files':files,'contract_sha256':supplied['contract_sha256'],'source_sha256':before}
    (copy/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    wsl=['wsl','-d',runtime['distribution'],'-u',runtime['user'],'--cd','/home/'+runtime['user'],'--exec']
    docker=wsl+['docker','--context','rootless'];container=None;completion=None;code=1;expired=False;started=time.monotonic()
    result={'scope':'dt-migration','source_sha256':before,'selected_inputs':files,'input_manifest_sha256':sha(input_path),'runtime':runtime,'release_admission':False}
    def call(cmd,**kwargs):return subprocess.run(cmd,capture_output=True,timeout=30,check=True,**kwargs)
    try:
        info=json.loads(call(docker+['info','--format','{{json .}}']).stdout)
        if 'name=rootless' not in info['SecurityOptions'] or info['CgroupDriver']!='systemd' or info['CgroupVersion']!='2':raise ValueError('Rootless resource controls unavailable.')
        actual=call(docker+['image','inspect',runtime['image'],'--format','{{.Id}}'],text=True).stdout.strip()
        if actual!=runtime['image']:raise ValueError('Pinned image unavailable.')
        helper=call(wsl+['sha256sum',runtime['retention_helper']],text=True).stdout.split()[0]
        if helper!=runtime['retention_helper_sha256']:raise ValueError('Retained helper changed.')
        linux=runtime['construction_root']+'/decision-tracker-migration-'+attempt.name
        archive=io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as tar:
            for p in sorted(copy.rglob('*')):
                if p.is_file():tar.add(p,arcname=p.relative_to(copy).as_posix(),recursive=False)
        raw=archive.getvalue()
        if len(raw)>64*1024**2:raise ValueError('Transfer capacity exceeded.')
        unpack="from pathlib import Path; import sys,tarfile,io; p=Path(sys.argv[1]); p.mkdir(); a=tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:'); ms=a.getmembers(); assert len(ms)<8192 and all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in ms); a.extractall(p/'input',filter='data')"
        call(wsl+['/usr/bin/python3','-c',unpack,linux],input=raw)
        name='decision-tracker-migration-'+attempt.name
        create=['create','--name',name,'--network','none','--read-only','--user','65532:65532','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--cpus','1','--memory','512m','--memory-swap','512m','--pids-limit','64','--ulimit','nofile=128:128','--ulimit','fsize=67108864:67108864',
            '--tmpfs','/tmp:rw,noexec,nosuid,size=256m,mode=1777','--tmpfs','/out:rw,noexec,nosuid,size=64m,nr_inodes=8192,mode=1777',
            '--log-driver','local','--log-opt','compress=false','--log-opt','max-size=1m','--log-opt','max-file=1',
            '--mount','type=bind,source='+linux+'/input,target=/input,readonly',
            '--mount','type=bind,source='+linux+'/input/tools/linux_proof_driver.py,target=/measure.py,readonly',
            '--mount','type=bind,source='+runtime['retention_helper']+',target=/retain.py,readonly',
            '--env','PYTHONDONTWRITEBYTECODE=1',runtime['image'],'-B','/retain.py']
        container=call(docker+create,text=True).stdout.strip();inspection=json.loads(call(docker+['inspect',container]).stdout)[0];h=inspection['HostConfig']
        if not (inspection['Image']==runtime['image'] and inspection['Config']['User']=='65532:65532' and h['NetworkMode']=='none' and h['ReadonlyRootfs'] and h['CapDrop']==['ALL'] and any('no-new-privileges' in s for s in h['SecurityOpt']) and h['NanoCpus']==1000000000 and h['Memory']==536870912 and h['MemorySwap']==536870912 and h['PidsLimit']==64):raise ValueError('Actual isolation controls differ.')
        if {m['Destination']:m['RW'] for m in inspection['Mounts']}!={'/input':False,'/measure.py':False,'/retain.py':False}:raise ValueError('Unexpected mount or writable input.')
        if 'size=64m' not in h['Tmpfs']['/out'] or 'size=256m' not in h['Tmpfs']['/tmp']:raise ValueError('Scratch bounds differ.')
        limits={x['Name']:(x['Soft'],x['Hard']) for x in h['Ulimits']}
        if limits.get('nofile')!=(128,128) or limits.get('fsize')!=(67108864,67108864):raise ValueError('File/descriptor limits differ.')
        (attempt/'create-inspect.json').write_text(json.dumps(inspection,indent=2),encoding='utf-8')
        call(docker+['start',container]);deadline=time.monotonic()+args.budget_seconds
        while time.monotonic()<deadline:
            snapshot=subprocess.run(docker+['exec',container,'/usr/bin/python','-c',"from pathlib import Path; p=Path('/out/completion.json'); print(p.read_text() if p.exists() else '{}')"],capture_output=True,timeout=15)
            if snapshot.returncode:break
            if len(snapshot.stdout)>4096:raise ValueError('Completion capacity exceeded.')
            observed=json.loads(snapshot.stdout)
            if 'exit' in observed:completion=observed;break
            time.sleep(1)
        if completion is None:
            expired=True;call(docker+['kill',container])
        else:
            export="from pathlib import Path; import sys,tarfile; p=Path('/out'); fs=list(p.rglob('*')); assert len(fs)<8192 and all(not f.is_symlink() for f in fs); assert sum(f.stat().st_size for f in fs if f.is_file())<=67108864;\nwith tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as a:\n for f in fs:\n  if f.is_file():a.add(f,arcname=f.relative_to(p),recursive=False)\n"
            output=call(docker+['exec',container,'/usr/bin/python','-c',export]).stdout
            if len(output)>80*1024**2:raise ValueError('Evidence transfer capacity exceeded.')
            with tarfile.open(fileobj=io.BytesIO(output)) as tar:
                members=tar.getmembers()
                if len(members)>=8192 or not all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members):raise ValueError('Unsafe evidence archive.')
                tar.extractall(attempt/'evidence',filter='data')
            call(docker+['exec',container,'/usr/bin/python','-c',"from pathlib import Path; Path('/out/export-acknowledged').touch()"])
            call(docker+['wait',container]);state=json.loads(call(docker+['inspect',container]).stdout)[0]['State']
            report=json.loads((attempt/'evidence/calamum-report.json').read_text())
            code=0 if completion['exit']==0 and report['result']=='pass' and state['ExitCode']==0 and not state['OOMKilled'] else 1
            result['state']=state;result['native_run_id']=report['run_id']
        logs=subprocess.run(docker+['logs',container],capture_output=True,timeout=15)
        (attempt/'container.stdout.txt').write_bytes(logs.stdout);(attempt/'container.stderr.txt').write_bytes(logs.stderr)
    except Exception as exc:
        result['failure']=str(exc);raise
    finally:
        if container:
            try:
                logs=subprocess.run(docker+['logs',container],capture_output=True,timeout=15)
                (attempt/'container.stdout.txt').write_bytes(logs.stdout)
                (attempt/'container.stderr.txt').write_bytes(logs.stderr)
                inspection=subprocess.run(docker+['inspect',container],capture_output=True,timeout=15)
                (attempt/'terminal-inspect.json').write_bytes(inspection.stdout)
            except Exception as exc:
                result['terminal_capture_failure']=str(exc)
            subprocess.run(docker+['rm','-f',container],capture_output=True,timeout=15)
        after={p.relative_to(root).as_posix():sha(p) for p in source_files(root) if not p.relative_to(root).as_posix().startswith('.local/')}
        unchanged=before==after
        result.update(exit_code=code if unchanged else 1,timeout=expired,source_unchanged=unchanged,completion=completion,elapsed_seconds=time.monotonic()-started)
        (attempt/'proof-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'exit_code':result['exit_code'],'timeout':expired,'source_unchanged':unchanged,'evidence':str(attempt)}))
    return result['exit_code']
