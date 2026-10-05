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
