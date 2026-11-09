# Private agent workflow: built-in Postgres

This guidance belongs in the skill, not on public v8r.dev pages or in generated
app UIs. Use it for new apps needing relational persistence, adding a database to
an existing v8r app, or explicitly regenerating a lost/compromised DB password.
An app may keep an existing database provider; do not migrate data implicitly.

## API contract and availability

Authenticate with the invited owner's GitHub CLI token. A project owner or a
control-plane admin may operate on an active project. A CDN/app-login `v8r-`
token does **not** authorize these endpoints. Never copy the GitHub token into
the deployed app, and never use the control plane's Postgres admin credential.

| Operation               | Request                                                                                 | Response                                                                                                  |
| ----------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Claim a new app with DB | `POST /api/projects` with `namespace`, `name`, `targetKind: "vercel"`, `database: true` | 201 with one-time `database.url`                                                                          |
| Check existing DB       | `GET /api/projects/:namespace/database`                                                 | 200 `{ database: { exists: false } }` or `exists: true` plus host/port/name/username/sslmode; no password |
| Add DB to existing app  | `POST /api/projects/:namespace/database`                                                | 201 with one-time `database.url`; 409 if already provisioned                                              |
| Regenerate credential   | `POST /api/projects/:namespace/database/rotate`                                         | 200 with one-time `database.url`; preserves database, role, schema and data                               |

These endpoints must be deployed in the control plane before use. Verify
`GET /api/me` works first. If an owned project's database endpoint returns an HTML
404, or the new endpoint is unavailable, report that the control-plane release is
missing. Do not fall back to SSH, shared credentials, or a different provider.
The repo README describing an API is not proof that production serves it.

## Capture secrets without printing them

Use the bundled helper at `<skill-dir>/scripts/database.mjs` (Node 20+ and `gh`).
It uses the same API, makes no automatic retries, and reserves a mode-0600 file
before a mutation. The output file must not already exist. Use an ignored private
directory outside the app's deployment source and leave shell tracing disabled:

```sh
umask 077
V8R_DB_DIR=$(mktemp -d)
# Substitute the actual skill directory and namespace below.
node <skill-dir>/scripts/database.mjs status <namespace>
```

Choose exactly one mutation:

```sh
# Brand new namespace: claim AND provision, before first production build.
node <skill-dir>/scripts/database.mjs create <namespace> "$V8R_DB_DIR/database-url" "Display name"

# Already-owned project with exists:false: add DB; do not claim again.
node <skill-dir>/scripts/database.mjs add <namespace> "$V8R_DB_DIR/database-url"

# Explicit request to regenerate a lost/compromised DB password:
node <skill-dir>/scripts/database.mjs rotate <namespace> "$V8R_DB_DIR/database-url"
```

Do not print, `cat`, commit, put in command arguments, or paste the URL into chat.
Do not retry with a different output file merely because the destination already
exists: it may contain the only copy of a successfully minted credential.

## Brand new app

1. Determine whether the app needs Postgres; inspect its existing persistence
   assumptions. Keep the app's chosen ORM (Drizzle/Prisma/etc.) and migration flow.
2. Create/link the Vercel project, then claim with `database: true` using `create`
   above. Do this **before** building/deploying code that requires `DATABASE_URL`.
   This replaces the normal non-DB claim step; do not claim the namespace twice.
3. Set `DATABASE_URL` as a server-only Vercel **production secret** via stdin:

   ```sh
   vercel env add DATABASE_URL --environment production --sensitive --yes --scope <scope> < "$V8R_DB_DIR/database-url"
   ```

   Check the linked project/scope first. Use `--force` only when intentionally
   replacing this app's existing value. Do not populate preview or development
   with production DB credentials by default. Never use `NEXT_PUBLIC_`/`VITE_`.

4. Add the app's schema and migration command. Run migrations from the server or
   trusted CLI with the saved URL in the process environment; read the file
   directly or redirect it into the process, never print it. Do not run migrations
   on every request. Use the app's existing secret-loading convention locally.
5. Deploy production, attach the domain, and verify a real persisted read/write
   through the deployed app. Remove only disposable test data. Verify again after
   a new request/process so an in-memory store cannot accidentally pass the test.
6. Once the deployment and recovery copy in the secret manager are verified,
   remove the temporary secret file/directory. Report success without the URL.

## Existing app that forgot its database

Check status first. If `exists:false`, run `add`, set `DATABASE_URL`, migrate,
redeploy, and verify persistence as above. If `exists:true`, keep the current
credential if it still works. The API cannot reveal the old password. A 409 from
`add` means "already exists", not "rotate automatically".

If the app currently stores data elsewhere, adding this DB does not copy that
data. Prepare and verify a migration separately before switching production's
`DATABASE_URL`. Never reset or recreate an existing DB to make onboarding work.

## Lost credential / intentional rotation

An explicit request to regenerate credentials authorizes the `rotate` operation.
Ordinary deployment or adding a database does not imply rotation. Identify all
consumers of the same role (web, workers, migration jobs) before rotating.

Rotation invalidates the old password for **new connections immediately**.
Already-authenticated sessions remain open. There is no dual-password grace
period; coordinate a brief maintenance window if continuous availability is
required. Save the new URL, replace `DATABASE_URL` in every authorized consumer
(`vercel env add ... --force`), and redeploy/restart their pools. Updating the
Vercel environment alone does not update existing deployments.

Verify new connections and that existing data remains accessible. Do not run
schema reset or seed commands during rotation. If the response was lost, status
can confirm the database exists but cannot recover the new password. Preserve any
saved credential; explicitly rotate again only when regeneration is still intended.
Never repeatedly rotate to debug authentication failures: check the deployed env,
project/scope, connection string, and redeployment first.

## Client setup

The returned URL uses `db.v8r.dev:5432` and `sslmode=verify-full`. Use the hostname,
not the IP: the public certificate is issued for the hostname. No custom CA file
is required; do not set `rejectUnauthorized:false` or disable TLS verification.

For node-postgres (server-only Node runtime, not browser/Edge code):

```ts
import { Pool } from "pg";
const url = new URL(process.env.DATABASE_URL!);
url.searchParams.delete("sslmode"); // pass verified TLS explicitly to pg
export const pool = new Pool({
  connectionString: url.toString(),
  ssl: { rejectUnauthorized: true },
  max: 5,
  connectionTimeoutMillis: 10_000,
  idleTimeoutMillis: 30_000,
});
```

Reuse a pool across requests. Each app role has a 20-connection ceiling across
all instances; small pools can still exhaust it at high serverless concurrency.
This is ordinary TCP Postgres: Neon-specific HTTP/WebSocket drivers are not a
drop-in client. Use `pg`/the ORM's TCP adapter; Prisma needs its Postgres adapter
appropriate to the installed version. Do not swap adapters blindly.

Apps own their database and can migrate schemas, but cannot create roles or
other databases. Backups and restores are operated by v8r; no R2 credentials are
needed in apps. Archiving a project preserves its database and does not revoke
connections. There is no self-service restore or database deletion API.

## Error recovery

- **401 / 403:** refresh GitHub login or obtain an invite; do not rotate DB passwords.
- **404:** confirm project ownership and active state; for rotation, confirm DB exists.
  An unavailable/HTML route indicates the control-plane feature has not shipped.
- **409 on claim:** check whether the intended project is already owned. Do not
  choose a new namespace automatically when recovering a partial claim.
- **409 on add:** preserve the existing DB; reuse its secret or explicitly rotate.
- **503 after claim:** project creation may already have succeeded. Check the
  project and DB status; `add` can finish an interrupted provision. Never loop claims.
- **Network error/503 after add or rotate:** outcome may be committed. Do not auto-retry
  the mutation. Inspect saved output and status, then choose recovery deliberately.
- **Connection failures after saving a secret:** check redeployment, hostname/TLS,
  correct app/environment, and pool limits before considering another rotation.
