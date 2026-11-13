#!/usr/bin/env node
// Requires Node 20+ and an authenticated gh CLI. Never prints credentials.
import { execFileSync } from "node:child_process";
import { openSync, writeFileSync, closeSync, unlinkSync } from "node:fs";
import { resolve } from "node:path";

const [operation, namespace, output, displayName] = process.argv.slice(2);
const development = ["status-dev", "add-dev", "rotate-dev"].includes(operation);
const mode = development ? operation.slice(0, -4) : operation;
if (
  !["status", "create", "add", "rotate"].includes(mode) ||
  !/^[a-z0-9][a-z0-9-]{1,30}$/.test(namespace ?? "") ||
  (mode !== "status" && !output)
) {
  console.error(
    "Usage: node database.mjs <status|status-dev> <namespace> | <create|add|rotate|add-dev|rotate-dev> <namespace> <new-secret-file> [display-name]",
  );
  process.exit(2);
}
const base = new URL(process.env.V8R_API || "https://www.v8r.dev");
if (
  base.protocol !== "https:" &&
  !(
    base.protocol === "http:" &&
    ["localhost", "127.0.0.1"].includes(base.hostname)
  )
) {
  throw new Error("V8R_API must use HTTPS (except localhost for tests).");
}
let fd,
  saved = false;
try {
  const token = execFileSync("gh", ["auth", "token"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  }).trim();
  // Older control-plane releases ignore query parameters. Check explicit support
  // before any development mutation so an old server cannot rotate production.
  if (development) {
    const check = await fetch(
      new URL(
        `/api/projects/${namespace}/database?environment=development`,
        base,
      ),
      {
        headers: { Authorization: `Bearer ${token}` },
        redirect: "error",
        signal: AbortSignal.timeout(120_000),
      },
    );
    if (!check.ok || (await check.json()).environment !== "development")
      throw new Error(
        "Unexpected database environment support. Deploy the development-database control-plane release first.",
      );
  }
  // Reserve the destination before a mutation. Refuse to overwrite a saved URL
  // or follow a pre-existing symlink; the secret file is readable only by owner.
  if (mode !== "status") fd = openSync(resolve(output), "wx", 0o600);
  const path =
    mode === "create"
      ? "/api/projects"
      : `/api/projects/${namespace}/database${mode === "rotate" ? "/rotate" : ""}`;
  const response = await fetch(
    new URL(path + (development ? "?environment=development" : ""), base),
    {
      method: mode === "status" ? "GET" : "POST",
      redirect: "error",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      ...(mode === "create"
        ? {
            body: JSON.stringify({
              namespace,
              name: displayName || namespace,
              targetKind: "vercel",
              database: true,
            }),
          }
        : {}),
      signal: AbortSignal.timeout(120_000),
    },
  );
  if (!response.ok) {
    // Do not emit an arbitrary server response or auto-retry a mutation.
    throw new Error(
      `HTTP ${response.status}. See references/database.md for recovery; no automatic retry was made.`,
    );
  }
  const body = await response.json();
  if (development && body.environment !== "development")
    throw new Error("Unexpected database environment response.");
  if (mode === "status") {
    // Allowlist non-secret fields, even if an unexpected backend returns more.
    const d = body.database;
    if (typeof d?.exists !== "boolean")
      throw new Error("Unexpected database status response.");
    console.log(
      JSON.stringify(
        {
          exists: d.exists,
          ...(d.exists
            ? {
                host: d.host,
                port: d.port,
                name: d.name,
                username: d.username,
                sslmode: d.sslmode,
              }
            : {}),
        },
        null,
        2,
      ),
    );
  } else {
    const value = body.database?.url;
    if (typeof value !== "string")
      throw new Error(
        "Missing credential. Check status; do not repeat the claim.",
      );
    const url = new URL(value);
    if (
      !["postgres:", "postgresql:"].includes(url.protocol) ||
      url.hostname !== "db.v8r.dev" ||
      !url.password ||
      (development && !url.pathname.endsWith("_dev")) ||
      url.searchParams.get("sslmode") !== "verify-full"
    )
      throw new Error("Unexpected database credential response.");
    writeFileSync(fd, value, "utf8");
    saved = true;
    console.log(
      "Database URL saved to the requested private file. Install it as DATABASE_URL, then deploy and verify.",
    );
  }
} catch (error) {
  // Errors from gh/fetch can contain credentials or responses: never print them.
  const known =
    error instanceof Error &&
    /^(HTTP \d+\.|Unexpected database|Missing credential)/.test(error.message);
  console.error(
    known
      ? error.message
      : "Database operation failed. Check authentication, connectivity, and that the destination is new and writable. A mutation may have succeeded; check status before retrying.",
  );
  process.exitCode = 1;
} finally {
  if (fd !== undefined) {
    closeSync(fd);
    if (!saved) unlinkSync(resolve(output));
  }
}
