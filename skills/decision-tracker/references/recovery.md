## Start or reuse the local service

For an installed Windows deployment, run `decision-tracker service ensure-running --json` before data access. It starts or reuses the service without opening a browser. Pass `--deployment FILE` for a nondefault deployment. Do not install a startup task or keep it alive with polling; useful requests and bounded draft leases manage the 90-minute idle policy.

Normal selected-deployment startup/reuse and the bounded recovery below operate under
the actual standing Tracker task authority. They do not require a fresh operator approval
for each start. Reuse the explicitly selected deployment and existing principal; do not
replace installation, redeploy, change credentials, switch bindings or extend recovery
under that authority. An assignment-specific hold still controls its affected effects.
After permitted recovery fails or the essential outcome remains unknown, stop dependent
work and report the exact failure and retained request. Protected metadata access denial
requires the focused authorized access route; it is not a reason to switch deployments.

Use `--credential-principal NAME` only for an explicitly provisioned stored agent credential. It verifies the deployment before transmitting the token. Alternatively use `--token-env NAME` for the authorized external credential. Never fall back to operator/password access. A missing credential is an owner provisioning input, not permission to create or expand access.

On connection loss, allow at most one ensure-running attempt and one retry within a 60-second recovery budget, preserving exact payload, request ID and principal. If unavailable or uncertain, retain the request and report its state. Do not repeat a human password change automatically.

## Conflicts and uncertain outcomes

On a lost response, retry the **identical payload and request ID with the same principal**. Matching committed requests replay before stale-revision checks. Do not generate a new ID merely because the response was lost. Bound retries; if the service remains unavailable, retain the payload and report the unknown outcome.

On a confirmed revision conflict, fetch current state, compare it with the original and intended changes, and reconcile within authorization. Use a new request ID only for a deliberately revised request. Never silently advance preconditions and overwrite another actor's work. Identity mismatch, lost authorization, or disabled project requires resolving that condition; do not switch ledgers or credentials automatically.

JSON mode returns one envelope. Exit codes: 0 success, 2 invalid input, 3 revision/identity conflict, 4 authentication/permission, 5 availability/retry, 1 unexpected failure. Preserve meaningful failure evidence without credentials.

Retain a stale browser draft after remote closure; review current state and obtain authorized reopening instead of automatically advancing revisions.

Reusing a request ID with different content still fails.

