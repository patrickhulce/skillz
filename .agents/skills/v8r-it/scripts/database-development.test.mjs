import assert from "node:assert/strict";
import { test } from "node:test";
import {
  mkdtempSync,
  writeFileSync,
  readFileSync,
  existsSync,
  statSync,
  rmSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

test("development helper gates old servers, selects development, and saves private credentials", () => {
  const dir = mkdtempSync(join(tmpdir(), "v8r-helper-test-"));
  try {
    const mock = join(dir, "mock.mjs");
    writeFileSync(
      mock,
      `
import cp from 'node:child_process';
import { syncBuiltinESMExports } from 'node:module';
import { appendFileSync } from 'node:fs';
cp.execFileSync = () => 'test-token';
syncBuiltinESMExports();
globalThis.fetch = async (url, options) => {
  appendFileSync(process.env.REQUEST_LOG, JSON.stringify({url:String(url),method:options.method || 'GET'})+'\\n');
  const development = new URL(url).searchParams.get('environment') === 'development';
  const environment = development ? 'development' : 'production';
  const database = options.method === 'POST'
    ? {url:'postgres://app'+(development?'_dev':'')+':test-password@db.v8r.dev/app'+(development?'_dev':'')+'?sslmode=verify-full'}
    : {exists:false};
  return Response.json({...(!process.env.OLD_SERVER && {environment}),database});
};
`,
    );
    const script = fileURLToPath(new URL("database.mjs", import.meta.url));
    const run = (mode, old = false) => {
      const output = join(dir, `${mode}-${old}.secret`);
      const log = join(dir, `${mode}-${old}.log`);
      const result = spawnSync(
        process.execPath,
        ["--import", mock, script, mode, "demo", output],
        {
          encoding: "utf8",
          env: { ...process.env, REQUEST_LOG: log, OLD_SERVER: old ? "1" : "" },
        },
      );
      assert.ok(!`${result.stdout}${result.stderr}`.includes("test-password"));
      const calls = readFileSync(log, "utf8")
        .trim()
        .split("\n")
        .map(JSON.parse);
      return { result, calls, output };
    };
    for (const mode of ["add-dev", "rotate-dev"]) {
      const old = run(mode, true);
      assert.equal(old.result.status, 1);
      assert.equal(old.calls.length, 1);
      assert.equal(old.calls[0].method, "GET");
      assert.equal(existsSync(old.output), false);
      const current = run(mode);
      assert.equal(current.result.status, 0, current.result.stderr);
      assert.deepEqual(
        current.calls.map((c) => c.method),
        ["GET", "POST"],
      );
      for (const call of current.calls)
        assert.equal(
          new URL(call.url).searchParams.get("environment"),
          "development",
        );
      assert.ok(
        new URL(current.calls[1].url).pathname.endsWith(
          mode === "rotate-dev" ? "/database/rotate" : "/database",
        ),
      );
      assert.equal(
        new URL(readFileSync(current.output, "utf8")).pathname,
        "/app_dev",
      );
      assert.equal(statSync(current.output).mode & 0o777, 0o600);
    }
    const production = run("add");
    assert.equal(production.result.status, 0);
    assert.equal(production.calls.length, 1);
    assert.equal(new URL(production.calls[0].url).search, "");
    assert.equal(
      new URL(readFileSync(production.output, "utf8")).pathname,
      "/app",
    );
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
