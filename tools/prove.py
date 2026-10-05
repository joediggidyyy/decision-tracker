"""Bound native Calamum execution and retain a source-corresponding proof copy."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source_files(root):
    names = ["pyproject.toml", "README.md", "CONTRIBUTING.md", "SECURITY.md",
             "CHANGELOG.md", "AGENTS.md", ".gitignore", ".gitattributes",
             "requirements-dev.lock", ".calamum/project.json"]
    files = [root / p for p in names if (root / p).is_file()]
    for name in ["src", "tests", "tools", "catalog", "docs", "skills"]:
        files.extend(p for p in (root / name).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and not any(x.endswith(".egg-info") for x in p.parts))
    for name in ["home-preview.html","home.css","scoped-change.json"]:
        candidate=root / ".local/home-integration" / name
        if candidate.is_file():files.append(candidate)
    return sorted(set(files))

def job_for(proc):
    if os.name != "nt":
        raise RuntimeError("This bootstrap proof supervisor is qualified for Windows only.")
    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in
                    ["ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount"]]
    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]
    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        kernel.CloseHandle(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(proc._handle))):
        kernel.CloseHandle(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel, handle

def supervise(command, cwd, env, output, seconds):
    if seconds <= 0:
        raise ValueError("Budget must be positive.")
    with output.open("wb") as log:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        kernel = handle = None
        try:
            kernel, handle = job_for(proc)
            try:
                return proc.wait(timeout=seconds), False
            except subprocess.TimeoutExpired:
                kernel.CloseHandle(handle)
                handle = None
                proc.wait(timeout=10)
                return 124, True
        finally:
            if handle:
                kernel.CloseHandle(handle)
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definition", default="dt-bootstrap", choices=["dt-bootstrap", "dt-focus", "dt-integration", "dt-browser", "dt-live-focus", "dt-agent-workflow", "dt-auth-focus", "dt-account-browser", "dt-approval-focus", "dt-decision-form", "dt-action-forms","dt-projects-data"])
    parser.add_argument("--budget-seconds", type=int, default=60)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run = root / ".local/proofs" / uuid.uuid4().hex
    proof = run / "source"
    proof.mkdir(parents=True)
    before = {p.relative_to(root).as_posix(): sha(p) for p in source_files(root)}
    for rel in before:
        dest = proof / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, dest)
    env = dict(os.environ)
    # Do not inherit production tracker credentials or Calamum signing values.
    for key in list(env):
        if key.startswith(("DT_", "CALAMUM_")):
            env.pop(key)
    runtime_path = root / ".local/browser-runtime.json"
    if runtime_path.exists():
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        for key, variable in [("node_modules", "NODE_PATH"),
                              ("headless_executable", "PROOF_BROWSER_EXECUTABLE"),
                              ("browser_executable", "PROOF_FULL_BROWSER")]:
            path = Path(runtime[key])
            if not path.is_absolute() or not path.exists():
                raise ValueError("Browser proof runtime path is unavailable: " + key)
            env[variable] = str(path)
    env["DECISION_TRACKER_PROOF_WHEELS"] = str(root / ".local/wheels")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(proof / "src")
    env["CALAMUM_CONFIG_ROOT"] = str(run / "config")
    command = [str(Path(sys.executable).with_name("calamum.exe")), "test", "run",
               args.definition, "--project", str(proof), "--catalog-root", str(proof / "catalog"),
               "--runs-root", str(root / ".calamum/generated/runs"),
               "--job", args.definition, "--json"]
    started = time.time()
    result = {"source_sha256": before, "interpreter": sys.executable,
              "scope": args.definition, "started": started}
    try:
        code, expired = supervise(command, proof, env, run / "calamum-output.log", args.budget_seconds)
        after = {p.relative_to(root).as_posix(): sha(p) for p in source_files(root)}
        if before != after:
            code = 1
        result.update(exit_code=code, timeout=expired, source_unchanged=before == after)
        print(json.dumps({"exit_code": code, "timeout": expired,
                          "source_unchanged": before == after, "evidence": str(run)}))
        return code
    finally:
        result["elapsed_seconds"] = time.time() - started
        (run / "proof-manifest.json").write_text(json.dumps(result, indent=2) + "\n")

if __name__ == "__main__":
    raise SystemExit(main())
