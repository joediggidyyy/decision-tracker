"""Authentication principals and ephemeral same-origin browser sessions."""
from dataclasses import dataclass
import hashlib
import hmac
import os
import secrets
import threading
import time
from .errors import Fault, require

@dataclass(frozen=True)
class Principal:
    id: str
    projects: frozenset
    capabilities: frozenset
    auth_method: str = 'agent_bearer'

    def project(self, project_id):
        require("*" in self.projects or project_id in self.projects, "NOT_FOUND", "Project is unavailable.", 404)

    def need(self, capability):
        require(capability in self.capabilities, "FORBIDDEN", "This credential lacks the required capability.", 403,
                required_capability=capability)

class Auth:
    def __init__(self, config, environment=None):
        environment = os.environ if environment is None else environment
        self.entries, self.sessions, self.failures = [], {}, []
        self.lock = threading.RLock()
        names, hashes = set(), set()
        for item in config.principals:
            token = environment.get(item.token_env, "")
            require(len(token) >= 32 and token.isascii() and not any(c.isspace() for c in token),
                    "AUTH_CONFIG_REQUIRED", "Configure a sufficiently long injected credential before starting.", 503,
                    variable=item.token_env)
            value = hashlib.sha256(token.encode()).digest()
            require(value not in hashes and item.id not in names, "AUTH_CONFIG_INVALID", "Duplicate credential or principal.", 503)
            names.add(item.id); hashes.add(value)
            self.entries.append((value, Principal(item.id, frozenset(item.projects), frozenset(item.capabilities))))
        require(bool(self.entries), "AUTH_CONFIG_REQUIRED", "At least one principal is required.", 503)

    def bearer(self, token):
        value = hashlib.sha256(token.encode()).digest()
        for expected, principal in self.entries:
            if hmac.compare_digest(value, expected):
                return principal
        raise Fault("UNAUTHORIZED", "Authentication is required or has expired.", 401)

    def login(self, token):
        with self.lock:
            tick = time.monotonic()
            self.failures = [x for x in self.failures if tick-x < 60]
            require(len(self.failures) < 5, "RETRY_LATER", "Too many failed sign-in attempts.", 503)
            try:
                principal = self.bearer(token)
            except Fault:
                self.failures.append(tick)
                raise
            self.sessions = {k:v for k,v in self.sessions.items() if tick-v["seen"] < 1800 and tick-v["created"] < 28800}
            require(len(self.sessions) < 256, "RETRY_LATER", "Session capacity reached.", 503)
            sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self.sessions[sid] = {"principal": principal, "csrf": csrf, "created": tick, "seen": tick}
            return sid, self.sessions[sid]

    def session(self, sid, touch=True):
        with self.lock:
            value = self.sessions.get(sid)
            tick = time.monotonic()
            if not value or tick-value["seen"] >= 1800 or tick-value["created"] >= 28800:
                self.sessions.pop(sid, None)
                raise Fault("UNAUTHORIZED", "Your session expired. Sign in again.", 401)
            if touch:value["seen"] = tick
            return value

    def logout(self, sid):
        with self.lock:
            self.sessions.pop(sid, None)
