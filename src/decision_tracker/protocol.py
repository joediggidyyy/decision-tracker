"""Strict Windows URI entry point; no shell or arbitrary URI arguments."""
import sys
from pathlib import Path

def main(argv):
    if len(argv)!=2 or argv[1].lower() not in ('decision-tracker://open','decision-tracker://open/'):
        return 2
    from decision_tracker.deployment import open_app
    try:open_app(Path(argv[0]));return 0
    except Exception:
        # A windowless protocol handler must give the owner a visible, nonsecret error.
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,'Decision Tracker could not start. Use service ensure-running in the local CLI for details.','Decision Tracker',0x10)
        return 1

if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main(sys.argv[1:]))
