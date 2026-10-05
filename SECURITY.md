# Security

[Home](README.md) · [Operations](docs/operations.md) · [Verification](docs/verification.md)

## Report a concern privately

Email [Joe Waller](mailto:joe.waller@polymath-global.com) at **joe.waller@polymath-global.com**. Use a subject containing the exact words **Security Alert**, followed by the project name and a brief description:

```text
Security Alert — Decision Tracker — brief description
```

A correctly titled email sends Joe an alert. Describe the affected version, observed behavior, impact and safe reproduction steps. Exclude passwords, tokens and private decision records. Do not use GitHub issues, pull requests, comments or other repository messages to report vulnerabilities.

After emailing, an optional call or text to **948.888.2336** is encouraged for urgent concerns. It does not replace the email.

Decision Tracker is an internal alpha for local use. No production support window or response-time commitment is declared.

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

See [verification](docs/verification.md) for actual proof coverage and [operations](docs/operations.md) for recovery. Passing synthetic tests does not establish owner acceptance or production qualification.

---

<p align="center">Maintained by Polymath Global</p>
