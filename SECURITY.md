# Security

Decision Tracker is pre-release scaffolding. It has no operational application
service and no production-supported release.

Report concerns privately to the repository owner through an existing trusted
private channel. Do not post credentials or sensitive project records in issues.
No response-time commitment is implied.

The application contract requires loopback-only hosting, explicit project identity,
scoped authentication, revision conflict protection, immutable decision history,
path containment, inert user text and verified recovery artifacts. These controls
are planned, not yet implemented or certified.

Credentials arrive through environment variables or approved handles. Documentation
may name variables, never their values. Real keys, tokens, local overlays, database
files, backups and exports must stay outside tracked source.

Local Calamum checksums establish byte integrity, not signer identity. Signing is
optional tooling capability and is not represented as active trust without
owner-provided authority. Monitoring or packet-capture capability availability
does not authorize collection.
