"""Safe domain errors shared by every interface."""
class Fault(Exception):
    def __init__(self, code, message, status=422, details=None, recovery="Correct the request and retry."):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details, self.recovery = details or {}, recovery

def require(condition, code, message, status=422, **details):
    if not condition:
        raise Fault(code, message, status, details)

def missing():
    raise Fault("NOT_FOUND", "The requested object is unavailable.", 404)

def stale(revision):
    raise Fault("STALE_REVISION", "The record changed since it was read.", 409,
                {"current_revision": revision}, "Reload, reconcile your changes and submit a new request.")
