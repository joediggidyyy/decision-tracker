# Security

Decision Tracker is an internal alpha local application. It is not a production-supported or publicly hosted release. Report concerns privately to the repository owner through an existing trusted channel. Do not include credentials or private records in public issues.

## Implemented boundaries

- Fixed loopback binding, exact Host/Origin checks, no proxy trust or permissive CORS.
- Durable salted scrypt human password verifiers; separate individually revocable agent-token digests.
- Purpose-bound expiring setup/recovery codes, persistent rate bounds and atomic session epoch revocation.
- CLI-only recovery over an owner-restricted local named pipe; current-user DPAPI for retained agent secrets.
- Nonce/HMAC deployment identity before stored agent credential transmission.
- Explicit per-principal project/capability scopes; no client-supplied authority escalation.
- HttpOnly SameSite=Strict browser sessions, idle/absolute expiry and same-origin CSRF checks.
- Explicit ledger identity, revision conflicts and durable request retries.
- Transactional changes, immutable history and bounded candidate-only import/recovery.
- Contained local paths with symlink/junction rejection.
- Packaged offline assets, restrictive CSP and user text rendered through textContent.

Local account compromise is outside the application boundary. Loopback HTTP is deliberately local and not suitable for LAN exposure. The session cookie uses HTTP on loopback, so Secure is not set; do not reverse proxy this alpha to a network listener.

No credential belongs in a URL, command argument, tracked file or report. Runtime data, exports, backups and evidence remain ignored. Reference locators are inert evidence text and are never automatically fetched.

Checksums prove byte correspondence, not signer identity. Calamum signing and monitoring are not represented as active trust. No monitor/capture activation, remote permission change or public deployment is included.

See docs/verification.md for actual proof coverage and docs/operations.md for recovery. Passing synthetic tests does not establish owner acceptance or production qualification.
