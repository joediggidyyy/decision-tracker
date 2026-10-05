import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from decision_tracker.credentials import Credentials, hash_password, verify_password
from decision_tracker.lifecycle import Lifecycle
from decision_tracker.errors import Fault

OLD="Synthetic initial password 2026"
NEW="Synthetic replacement password 2026"

def test_setup_change_recovery_and_agent_separation(tmp_path):
    store=Credentials(tmp_path/"auth.sqlite",initialize=True)
    code=store.issue("bootstrap");store.redeem("bootstrap",code,OLD,OLD)
    with pytest.raises(Fault):store.redeem("bootstrap",code,OLD,OLD)
    epoch=store.check_password(OLD)
    key,token=store.token_create("agent")
    store.change(OLD,NEW,NEW,epoch)
    with pytest.raises(Fault):store.check_password(OLD)
    assert store.token_principal(token)=="agent"
    reset=store.issue("recovery")
    with pytest.raises(Fault):store.redeem("bootstrap",reset,OLD,OLD)
    with pytest.raises(Fault):store.check_password(NEW)
    store.redeem("recovery",reset,OLD,OLD)
    assert store.check_password(OLD)>epoch
    store.token_revoke(key)
    with pytest.raises(Fault):store.token_principal(token)

def test_concurrent_redeem_single_winner_and_expiry(tmp_path):
    tick=[1000.];store=Credentials(tmp_path/"auth.sqlite",initialize=True,clock=lambda:tick[0])
    code=store.issue("bootstrap")
    def redeem():
        try:store.redeem("bootstrap",code,OLD,OLD);return True
        except Fault:return False
    with ThreadPoolExecutor(2) as pool:assert sum(pool.map(lambda _:redeem(),range(2)))==1
    code=store.issue("recovery");tick[0]+=901
    with pytest.raises(Fault):store.redeem("recovery",code,NEW,NEW)

def test_password_encoding_and_rate_window(tmp_path):
    first=hash_password(OLD);second=hash_password(OLD)
    assert first!=second and verify_password(OLD,first)
    assert not verify_password(OLD,first.replace("131072","999999999"))
    clock=[1000.];store=Credentials(tmp_path/"auth.sqlite",initialize=True,clock=lambda:clock[0])
    code=store.issue("bootstrap");store.redeem("bootstrap",code,OLD,OLD)
    for _ in range(5):
        with pytest.raises(Fault):store.check_password("wrong")
    with pytest.raises(Fault) as caught:store.check_password(OLD)
    assert caught.value.status==429
    clock[0]+=301;assert store.check_password(OLD)==1

def test_idle_admission_draft_grace_and_stop():
    tick=[0.];life=Lifecycle(enabled=True,clock=lambda:tick[0]);life.start()
    tick[0]=5399;assert not life.stop()
    life.enter();tick[0]=6000;assert not life.stop();life.leave()
    tick[0]=11399;assert not life.stop()
    lease=life.lease("session","alpha","uuid","tab")
    tick[0]+=181;assert not life.stop()
    tick[0]+=5400;assert life.stop()
    with pytest.raises(Fault):life.enter()
    assert life.active==0


def test_windows_protected_bundle_and_local_pipe(tmp_path):
    import os
    if os.name!="nt":pytest.skip("Windows adapter")
    from decision_tracker.windows_local import protect_path,save_bundle,read_bundle,AdminPipe,admin_request
    from uuid import uuid4
    protect_path(tmp_path)
    path=tmp_path/"bundle.bin";value={"synthetic":"Synthetic protected test only"}
    save_bundle(path,value);assert read_bundle(path)==value
    assert b"Synthetic protected" not in path.read_bytes()
    deployment=str(uuid4());server=AdminPipe(deployment,lambda request:{"operation":request["operation"]})
    server.start()
    try:assert admin_request(deployment,"status")=={"operation":"status"}
    finally:server.close()
    assert not server.thread.is_alive()


def test_draft_ownership_capacity_and_revocation_grace():
    tick=[0.];life=Lifecycle(enabled=True,clock=lambda:tick[0]);life.start()
    leases=[life.lease('owner','alpha','uuid',str(i)) for i in range(8)]
    with pytest.raises(Fault):life.lease('owner','alpha','uuid','overflow')
    with pytest.raises(Fault):life.release('other',leases[0]['lease_id'])
    with pytest.raises(Fault):life.lease('owner','other-project','uuid','0',leases[0]['lease_id'])
    with pytest.raises(Fault):life.stop(explicit=True)
    tick[0]=6000;assert not life.stop(valid=lambda _:False)
    assert not life.leases
    tick[0]=11399;assert not life.stop()
    tick[0]=11400;assert life.stop()


def test_clock_rollback_invalidates_code_and_missing_store_fails(tmp_path):
    with pytest.raises(Fault):Credentials(tmp_path/'absent.sqlite')
    tick=[1000.];store=Credentials(tmp_path/'auth.sqlite',initialize=True,clock=lambda:tick[0]);code=store.issue('bootstrap')
    tick[0]=900
    with pytest.raises(Fault):store.redeem('bootstrap',code,OLD,OLD)
    tick[0]=1001
    with pytest.raises(Fault):store.redeem('bootstrap',code,OLD,OLD)


def test_stop_admission_race_never_stops_active_work():
    for _ in range(20):
        life=Lifecycle(enabled=True);life.start();barrier=threading.Barrier(2)
        def admit():
            barrier.wait()
            try:life.enter();return True
            except Fault:return False
        def stop():
            barrier.wait()
            try:return life.stop(explicit=True)
            except Fault:return False
        with ThreadPoolExecutor(2) as pool:
            a=pool.submit(admit);b=pool.submit(stop);entered,stopped=a.result(),b.result()
        assert entered!=stopped
        if entered:assert life.state=='RUNNING' and life.active==1;life.leave()
        else:assert life.state=='DRAINING' and life.active==0


def test_interrupted_token_publication_keeps_previous_active(tmp_path):
    import os
    if os.name!='nt':pytest.skip('Windows adapter')
    from decision_tracker.deployment import initialize,load,atomic_json
    from decision_tracker.administration import recover_token_journal
    from decision_tracker.credentials import digest
    path=tmp_path/'deployment'/'deployment.json';initialize(path,data_root=tmp_path/'data');value,cfg=load(path)
    store=Credentials(__import__('pathlib').Path(cfg.auth_store));old,raw=store.token_create('agent');new,pending=store.token_create('agent',state='pending')
    atomic_json(path.parent/'token-journal.json',{'new_id':new,'old_id':old,'principal':'agent','digest':digest(pending)})
    recover_token_journal(value,store)
    assert store.token_principal(raw)=='agent'
    with pytest.raises(Fault):store.token_principal(pending)


def test_corrupt_protected_bundle_refused(tmp_path):
    import os
    if os.name!='nt':pytest.skip('Windows adapter')
    from decision_tracker.windows_local import read_bundle
    path=tmp_path/'secrets.bin';path.write_bytes(b'Not a DPAPI credential bundle')
    with pytest.raises(Fault) as caught:read_bundle(path)
    assert caught.value.code=='SETUP_REQUIRED'
