import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { spawn } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  statSync,
  existsSync,
  rmSync,
} from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

test("helper captures one-time secrets, prevents overwrites, redacts status and never retries mutations", async () => {
  const dir = mkdtempSync(join(tmpdir(), "v8r-agent-db-"));
  const bin = join(dir, "bin");
  mkdirSync(bin);
  writeFileSync(join(bin, "gh"), "#!/bin/sh\nprintf fake-gh-token", {
    mode: 0o755,
  });
  const credential =
    "postgresql://app_demo:secret-do-not-print@db.v8r.dev:5432/app_demo?sslmode=verify-full";
  const calls = [];
  let fail = false;
  const server = createServer(async (req, res) => {
    let body = "";
    for await (const chunk of req) body += chunk;
    calls.push({
      method: req.method,
      url: req.url,
      body,
      auth: req.headers.authorization,
    });
    res.setHeader("Content-Type", "application/json");
    if (fail) {
      res.writeHead(503);
      res.end(JSON.stringify({ error: credential }));
      return;
    }
    res.end(
      JSON.stringify({
        database:
          req.method === "GET"
            ? {
                exists: true,
                host: "db.v8r.dev",
                port: 5432,
                name: "app_demo",
                username: "app_demo",
                sslmode: "verify-full",
                url: credential,
              }
            : { url: credential },
      }),
    );
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const api = `http://127.0.0.1:${server.address().port}`;
  const run = (args) =>
    new Promise((resolve, reject) => {
      const child = spawn(
        process.execPath,
        [fileURLToPath(new URL("database.mjs", import.meta.url)), ...args],
        {
          env: {
            ...process.env,
            PATH: `${bin}:${process.env.PATH}`,
            V8R_API: api,
          },
        },
      );
      let out = "";
      child.stdout.on("data", (c) => (out += c));
      child.stderr.on("data", (c) => (out += c));
      child.on("error", reject);
      child.on("close", (code) => resolve({ code, out }));
    });
  try {
    const output = join(dir, "url");
    const create = await run(["create", "demo", output, "Demo"]);
    assert.equal(create.code, 0, create.out);
    assert.ok(!create.out.includes("secret-do-not-print"));
    assert.equal(readFileSync(output, "utf8"), credential);
    assert.equal(statSync(output).mode & 0o777, 0o600);
    assert.equal(calls[0].auth, "Bearer fake-gh-token");
    assert.deepEqual(JSON.parse(calls[0].body), {
      namespace: "demo",
      name: "Demo",
      targetKind: "vercel",
      database: true,
    });
    assert.equal((await run(["rotate", "demo", output])).code, 1);
    assert.equal(calls.length, 1);
    assert.equal(readFileSync(output, "utf8"), credential);
    const status = await run(["status", "demo"]);
    assert.equal(status.code, 0);
    assert.ok(!status.out.includes("secret-do-not-print"));
    assert.equal(JSON.parse(status.out).exists, true);
    assert.equal((await run(["add", "demo", join(dir, "add")])).code, 0);
    assert.equal(calls.at(-1).url, "/api/projects/demo/database");
    assert.equal((await run(["rotate", "demo", join(dir, "rotate")])).code, 0);
    assert.equal(calls.at(-1).url, "/api/projects/demo/database/rotate");
    fail = true;
    const before = calls.length;
    const failed = await run(["rotate", "demo", join(dir, "failed")]);
    assert.equal(failed.code, 1);
    assert.equal(calls.length, before + 1);
    assert.ok(!failed.out.includes("secret-do-not-print"));
    assert.equal(existsSync(join(dir, "failed")), false);
  } finally {
    server.close();
    await once(server, "close");
    rmSync(dir, { recursive: true, force: true });
  }
});
