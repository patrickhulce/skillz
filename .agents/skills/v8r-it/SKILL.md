---
name: v8r-it
description: Deploy an arbitrary app to Vercel and onto the v8r platform, giving it a public hostname at <namespace>.v8r.app and optional asset hosting at cdn.v8r.app/n/<namespace>/. Use when the user says "v8r it", "v8r-it", "deploy to v8r", or wants an app on *.v8r.app or assets on cdn.v8r.app.
disable-model-invocation: true
---

# v8r-it

Ship an app onto the v8r platform. End state:

- App deployed to Vercel and serving at `https://<namespace>.v8r.app`
- Listed on the public showcase at `https://www.v8r.dev/apps`
- (Optional) asset pipeline to `https://cdn.v8r.app/n/<namespace>/` via short-lived R2 credentials

## Architecture in one breath

`www.v8r.dev` is the invite-only control plane. It owns the `v8r.app` Cloudflare zone and writes CNAMEs for claimed namespaces. Agents authenticate with a GitHub CLI token (`Authorization: Bearer $(gh auth token)`). The first successful API call by an invited login provisions their account.

## Prerequisites

- `vercel` CLI installed and authed (`vercel whoami`)
- `gh` CLI installed and authed (`gh auth login` — the only v8r setup)
- A namespace in mind (see rules below)

Export once per session:

```bash
V8R_API=https://www.v8r.dev
V8R_AUTH="Authorization: Bearer $(gh auth token)"
```

## Checklist

```
- [ ] 1. Pick + validate a namespace
- [ ] 2. Deploy the app to Vercel (production)
- [ ] 3. Add <namespace>.v8r.app as a domain on the Vercel project
- [ ] 4. Claim the namespace via the Agent API (target: vercel)
- [ ] 5. Verify DNS, cert, and smoke test https://<namespace>.v8r.app
- [ ] 6. (Optional) mint CDN token via the Agent API + asset upload pipeline
```

## Step 1: Pick a namespace

Rules (enforced server-side): 2–31 chars, `^[a-z0-9][a-z0-9-]+$`.

Reserved (never claimable): `stream`, `www`, `cdn`, `api`, `app`, `admin`, `console`, `docs`, `static`, `assets`, `mail`, `ns1`, `ns2`, `_acme-challenge`.

Claiming reserves both `<namespace>.v8r.app` and the CDN prefix `n/<namespace>/`.

## Step 2: Deploy to Vercel

From the app's repo root:

```bash
vercel project add <project-name>          # once; lowercase, hyphens, no dots
vercel link --yes --project <project-name> --scope <scope>
vercel --prod --scope <scope> --yes
vercel git connect --scope <scope>         # optional: auto-deploy on push
```

- If `--scope` is ambiguous, the CLI prints the valid choices — rerun with one.
- Set env vars by piping values (never echo secrets): `printf '%s' "$VALUE" | vercel env add NAME production --scope <scope>`.

**Gotcha: empty deployment (0ms build, 404 on every route).** Fresh projects can be created with `framework: null` and skip the build entirely. Verify: `vercel inspect <deployment-url> --scope <scope>` must show a real build duration and routes. Fix by setting the preset via the API, then redeploy:

```bash
TOKEN=$(python3 -c "import json,os; print(json.load(open(os.path.expanduser('~/Library/Application Support/com.vercel.cli/auth.json')))['token'])")
curl -X PATCH "https://api.vercel.com/v9/projects/<project>?teamId=<team-id>" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"framework":"nextjs"}'   # or the right preset
```

**Gotcha: 302 to `vercel.com/sso-api` on every URL.** Deployment Protection SSO is gating production. Make it preview-only:

```bash
curl -X PATCH "https://api.vercel.com/v9/projects/<project>?teamId=<team-id>" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"ssoProtection":{"deploymentType":"preview"}}'
```

Smoke test before continuing: `curl -s -o /dev/null -w "%{http_code}\n" https://<project>.vercel.app` → expect 200.

## Step 3: Attach the v8r hostname in Vercel

```bash
vercel domains add <namespace>.v8r.app <project> --scope <scope>
```

It will report unverified until Step 4 lands — that's expected. Do **not** create DNS records for `v8r.app` yourself; the control plane owns that zone.

## Step 4: Claim the namespace (Agent API)

Preflight, then claim. Do not send the user to the console unless the API returns 401/403 (then they need `gh auth login`, or an invite).

```bash
curl -s "$V8R_API/api/me" -H "$V8R_AUTH"
# expect {"login":"<github-login>","name":"...","role":"owner"|"admin"}

curl -s -X POST "$V8R_API/api/projects" -H "$V8R_AUTH" \
  -H "Content-Type: application/json" \
  -d "{\"namespace\":\"<namespace>\",\"name\":\"<Display Name>\",\"tagline\":\"<optional>\",\"targetKind\":\"vercel\"}"
# expect 201 {"namespace":"<namespace>","hostname":"<namespace>.v8r.app"}
```

Other `targetKind` values: `fly` (value: fly app name), `homelab` (value: Cloudflare tunnel ID, proxied), `external` (value: any CNAME target). Retarget later with `PUT /api/projects/<namespace>/deployment`. Re-check with `POST /api/projects/<namespace>/dns-check`.

Console UI at `https://www.v8r.dev/console/projects/new` is the fallback if the Agent API is unavailable.

## Step 5: Verify

```bash
dig +short CNAME <namespace>.v8r.app        # expect cname.vercel-dns.com.
vercel domains verify <namespace>.v8r.app --scope <scope>   # expect verified: true
curl -s "$V8R_API/api/projects/<namespace>" -H "$V8R_AUTH"   # dnsState should be synced
curl -s -o /dev/null -w "%{http_code}\n" https://<namespace>.v8r.app
```

Cert issuance takes a minute after DNS verifies; retry `000`/TLS errors briefly before debugging.

## Step 6 (optional): CDN asset pipeline

1. **Mint a token** (shown once, shape `v8r-<Base58>`):

```bash
curl -s -X POST "$V8R_API/api/projects/<namespace>/tokens" -H "$V8R_AUTH" \
  -H "Content-Type: application/json" -d '{"name":"default"}'
```

Set it on the Vercel project if the app will vend credentials itself:
`printf '%s' "$TOKEN" | vercel env add V8R_CDN_TOKEN production --scope <scope>`

2. **Vend short-lived R2 credentials** (docs: `https://www.v8r.dev/docs/cdn`):

```bash
curl -X POST "$V8R_API/api/cdn/credentials" \
  -H "Authorization: Bearer $V8R_CDN_TOKEN" \
  -H "Content-Type: application/json" -d '{"ttlSeconds": 900}'
```

Response: `{ endpoint, bucket, prefix, accessKeyId, secretAccessKey, sessionToken, publicBaseUrl, expiresAt }`. The prefix is always `n/<namespace>/`, derived from the token — never client-supplied.

3. **Upload with any S3 client** (`region: "auto"`, endpoint/creds from the response), keys under `prefix`. Public URL: `<publicBaseUrl>/<prefix><key>`.

Limits: TTL ≤ 900s; 20 vends per token per 15 min; 401 = missing/malformed token, 403 = valid token, wrong/revoked project.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/api/me` 401 | No/invalid GitHub token | `gh auth login` and retry with `$(gh auth token)` |
| `/api/me` 403 | Login not on the allowlist | User is not invited |
| `/api/me` 502 | GitHub unreachable | Retry; do not treat as a v8r outage immediately |
| Claim 409 | Namespace taken | Pick another name |
| 404 on all Vercel routes after deploy | 0ms build, `framework: null` | PATCH framework preset (Step 2), redeploy |
| 302 to `vercel.com/sso-api` | Deployment Protection on production | PATCH `ssoProtection` to `preview` (Step 2) |
| Vercel domain stuck unverified | DNS not applied or proxied | `PUT .../deployment` then `POST .../dns-check`; CNAME must be DNS-only |
| `curl` gives `000`/TLS error | Cert still provisioning | Wait ~60s, retry |
| credentials endpoint 401 | Bad/missing CDN bearer token | Re-mint via `POST .../tokens`; check `v8r-` prefix |
| Namespace rejected | Reserved or shape invalid | See Step 1 rules |
