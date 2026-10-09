import importlib.util
import os
from pathlib import Path
import sys

def test_supervisor_terminates_timeout(tmp_path):
    path = Path(__file__).resolve().parents[1] / "tools/prove.py"
    spec = importlib.util.spec_from_file_location("proof", path)
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    code, timeout = proof.supervise(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        tmp_path, dict(os.environ), tmp_path / "child.log", 1)
    assert code == 124
    assert timeout


def test_linux_adapter_rejects_changed_frozen_input_before_backend(tmp_path,monkeypatch):
    import json,hashlib
    from types import SimpleNamespace
    path=Path(__file__).resolve().parents[1]/"tools/prove_linux.py"
    spec=importlib.util.spec_from_file_location("linux_proof",path)
    adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    # The run function imports the shared proof helper through its tools path.
    monkeypatch.syspath_prepend(str(path.parent))
    root=tmp_path;local=root/".local";local.mkdir();item=local/"source.json";item.write_text("{}")
    runtime=local/"runtime.json";runtime.write_text(json.dumps({"distribution":"existing","user":"existing","construction_root":"/home/existing/construction","image":"sha256:"+"a"*64,"retention_helper":"/home/existing/construction/retain.py","retention_helper_sha256":"b"*64}))
    manifest=local/"inputs.json";manifest.write_text(json.dumps({"contract_sha256":"c"*64,"files":[{"project":"qa-engine","path":str(item),"sha256":"d"*64,"bytes":2}]}))
    import pytest
    with pytest.raises(ValueError,match="Selected input bytes changed"):
        adapter.run(root,SimpleNamespace(runtime_file=str(runtime),input_manifest=str(manifest),budget_seconds=180),lambda r:[])
    assert not (root/".local/proofs").exists()
