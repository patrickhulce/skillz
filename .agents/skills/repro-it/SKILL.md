---
name: repro-it
description: Construct a minimal, self-contained reproduction of a bug — a single copy-pasteable shell block that builds its own throwaway environment, pins exact versions, and exits non-zero on the buggy behavior. Use when the user asks for a repro, a minimal example, an MCVE, wants to isolate whether a bug is theirs or a dependency's, or is about to file an upstream issue.
---

# Repro It

A reproduction is not "here's my repo, run the tests". It is **one shell block a stranger can paste into a terminal** that builds its own environment from nothing, runs a handful of lines, and fails. If the reader has to install anything, clone anything, or guess anything, the repro has failed.

Optimize for the maintainer's first 60 seconds: they paste, they watch it fail, they believe you.

## The contract

Every repro you produce satisfies all seven:

| Property           | Meaning                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------- |
| **One block**      | A single fenced shell block. No "then create a file called…" prose between steps.            |
| **Self-installing**| It creates its own temp directory and installs its own dependencies. Never touches the cwd.  |
| **Low assumption** | Assumes only a package runner: `uv`, or `pnpm`/`npm`, or `deno`/`bun`. Nothing else.         |
| **Pinned**         | Every dependency, language version, and image tag is an exact version. No `latest`, no ranges.|
| **Failing**        | Exits non-zero — via an uncaught exception or a failed assertion that states expected vs actual. |
| **Minimal**        | Every remaining line is load-bearing. Deleting any one of them stops the reproduction.       |
| **Quiet**          | Almost no comments. The code is the argument; prose goes in the issue body, not the script.  |

## Workflow

### 1. State the claim in one sentence

Before writing code, write the sentence the repro exists to prove:

> With `pydantic==2.9.2`, `Model(x="3").x` returns `3` (int); it should return `"3"` (str).

This sentence dictates the assertion. If you can't write it, you don't understand the bug well enough to minimize it — go reproduce it messily first, then come back.

### 2. Reproduce it messily, in the real environment

Confirm the bug exists at all before minimizing. Run the failing test, hit the failing endpoint, whatever it takes. Capture the exact error text — you will use it to check that the minimized version reproduces *the same* failure, not a different one that happens to also fail.

### 3. Minimize by deletion

Copy the messy version into the template below and delete, repeatedly. After each deletion, re-run:

- Still fails the same way? Keep the deletion.
- Stops failing, or fails differently? Revert it — that line is load-bearing.

Delete in this order, coarsest first:

1. **Dependencies.** Drop each package. Most repros end up with one, sometimes zero.
2. **Your abstractions.** Classes, wrappers, config objects, DI, factories — inline them into literals.
3. **Data.** Shrink payloads to the smallest shape that still fails. A 400-key JSON fixture is almost never necessary; `{"a": 1}` usually is enough.
4. **Framework.** If it fails without FastAPI/React/Django, remove them. If it only fails with them, that fact is itself the bug report.
5. **Async / concurrency.** If it fails synchronously, make it synchronous.
6. **I/O.** Replace files, sockets, and databases with in-memory values — unless the I/O *is* the bug.

Stop when every remaining line is load-bearing. Ten lines is a good target; thirty is an acceptable ceiling; a hundred means keep going.

### 4. Prove the assertion is real

A repro that fails is worthless if it would fail on *anything*. Show the control:

- **Version A/B.** Re-run with the last known-good version pinned and show it passes. This is the single most persuasive thing you can hand a maintainer, and it hands them a bisect range for free.
- **Or the neighboring case.** If there is no good version, show the adjacent input that behaves correctly in the same script (`assert f(1) == 1` passing right above `assert f(2) == 2` failing).

### 5. Run the final block, then deliver

Run the exact block you are about to hand over, start to finish, in a fresh temp directory — not an earlier draft of it. Paste the output you actually saw. Never write down output you expect but didn't observe; a repro whose transcript doesn't match reality costs the maintainer more time than no repro at all.

Keep the scratch work out of the user's repository. The block lives in the chat or the issue body; if you need a file on disk, write it under `$(mktemp -d)` and say where it went.

Then hand over the block, the output, and the one-sentence claim — see [Filing it upstream](#filing-it-upstream).

## Templates

Adapt the payload; keep the scaffolding.

### Python — `uv` + PEP 723

`uv` reads the inline metadata header, builds an ephemeral env, and runs the script. Nothing is installed on the user's machine.

```bash
cd "$(mktemp -d)" && cat > repro.py <<'EOF'
# /// script
# requires-python = "==3.12.*"
# dependencies = ["pydantic==2.9.2"]
# ///
from pydantic import BaseModel

class M(BaseModel):
    x: int

print(M(x="3").x)
assert M(x="3").x == "3", "expected str passthrough, got coerced int"
EOF
uv run --python 3.12 repro.py
```

```
3
AssertionError: expected str passthrough, got coerced int
```

### Node — `pnpm` + temp project

```bash
cd "$(mktemp -d)" && pnpm init >/dev/null && pnpm add lodash@4.17.21 >/dev/null && cat > repro.mjs <<'EOF'
import assert from "node:assert/strict";
import _ from "lodash";

const out = _.merge({ a: [1, 2] }, { a: [3] });
console.log(out);
assert.deepEqual(out.a, [3], "expected replacement, got element-wise merge");
EOF
node repro.mjs
```

```
{ a: [ 3, 2 ] }
AssertionError [ERR_ASSERTION]: expected replacement, got element-wise merge
```

Notes that matter:

- Use the `.mjs` extension so you get ESM without a `"type": "module"` edit.
- `node:assert/strict` prints a real diff of actual vs expected — prefer it over `if (…) throw`.
- Redirect `pnpm` chatter to `/dev/null`; the only output should be the failure.
- Swap in `npm i`, `bun add`, or `deno`'s `npm:` specifiers if that is what the reporting ecosystem uses. Use the package manager the *project* uses, not your favorite.

### Browser — Playwright driven by `uv`

For DOM, rendering, and client-side JS bugs. One Python file scripts the whole browser session, and `uv` supplies Playwright.

```bash
cd "$(mktemp -d)" && cat > repro.py <<'EOF'
# /// script
# requires-python = "==3.12.*"
# dependencies = ["playwright==1.49.1"]
# ///
from playwright.sync_api import sync_playwright

HTML = """
<input id="q" value="a">
<script>
  const el = document.getElementById("q");
  el.value = el.value.trim().toUpperCase();
  window.__result = el.value;
</script>
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.set_content(HTML)
    result = page.evaluate("window.__result")
    browser.close()

print("result:", result)
assert result == "a", f"expected 'a', got {result!r}"
EOF
uv run --python 3.12 --with playwright==1.49.1 playwright install chromium
uv run --python 3.12 repro.py
```

The `playwright install chromium` line is unavoidable (browsers live outside the Python env, in `~/.cache/ms-playwright`), but it is idempotent and cached, so keep it in the block rather than making it a prerequisite the reader must know about.

`page.set_content()` covers most DOM bugs. When the bug needs a real origin — ES modules, CORS, cookies, service workers — serve a temp directory instead; see [references/templates.md](references/templates.md).

## Assertions and exit codes

The repro must fail by itself. A script that prints "notice how the value is wrong" and exits 0 puts the burden of judgment on the reader.

- **Assert the specific claim**, not a vague health check. `assert result == "a"` beats `assert result`.
- **Put expected and actual in the message.** `f"expected 'a', got {result!r}"`. The maintainer should be able to diagnose from the pasted output alone, without running anything.
- **Uncaught exceptions are fine** when the bug *is* the crash. Don't wrap a stack trace in `try`/`except` just to reformat it — the raw traceback is the evidence.
- **Print the state right before asserting.** One `print()` of the offending value makes the failure legible even in a screenshot.
- **Non-zero exit is the interface.** It's what lets the reader script the bisect.

## Comments

Near zero. The code is short enough to read.

Justified: a one-line header stating expected vs actual, and a marker on the single line that flips the behavior.

```python
assert M(x="3").x == "3"  # 2.8.2: passes. 2.9.2: fails, returns int 3.
```

Not justified: explaining what `BaseModel` is, narrating each step, or apologizing for the example being contrived. Delete all of it.

## Pinning versions

Ranges make a repro rot. Resolve the real version and write it down:

```bash
uv pip index versions pydantic     # Python
npm view lodash versions --json    # Node — last entry is latest
npm view lodash version            # just the latest
```

Pin the language runtime too (`requires-python = "==3.12.*"`, `--python 3.12`, or a Node version in the prose). "Fails on Python 3.12, passes on 3.11" is frequently the whole bug.

## Hermeticity

The repro must not depend on anything about *your* machine.

- **Always `cd "$(mktemp -d)"`.** Never write into the user's cwd, never `rm -rf` a path you constructed.
- **No global installs.** No `pip install`, no `npm i -g`, no `brew`, no `sudo`, no venv the reader has to activate.
- **No private resources.** No internal registries, VPN-only hosts, credentials, or company-specific images. If the bug needs a server, start one inside the script on port 0 and read back the assigned port.
- **No network flakiness.** Hitting a live third-party API means the maintainer sees a timeout instead of your bug. Use a local server or a literal fixture — unless the network call *is* the bug, in which case pick a stable endpoint like `https://httpbin.org/get` and say so.
- **Determinism.** Seed any RNG, avoid wall-clock and timezone dependence, and don't rely on dict/set iteration order — unless one of those is the bug.
- **Run it twice, in a fresh shell.** A repro that only fails the first time (or only with your shell's env vars) is not done.

## Intermittent bugs

If it fails 1-in-N, say so and make the script prove it — loop inside the repro and report the rate rather than handing over something that passes on the maintainer's first try:

```python
fails = sum(1 for _ in range(200) if not check())
assert fails == 0, f"{fails}/200 iterations produced the wrong result"
```

## When the bug is in your own code

Same discipline, one extra decision: the repro should install your package from a published version or a git ref, not from a working tree the reader doesn't have.

```bash
# published
uv run --python 3.12 --with "mypkg==1.4.0" repro.py
# unreleased
uv run --python 3.12 --with "mypkg @ git+https://github.com/me/mypkg@abc1234" repro.py
```

If the bug only exists in uncommitted local code, push a branch first. A repro that can't be run by the person you're sending it to isn't a repro — it's a note to yourself.

## Filing it upstream

Deliver, in this order:

1. **The claim.** One sentence: expected vs actual.
2. **The block.** The shell block, verbatim, in one fence.
3. **The output.** What it printed when you ran it, trimmed to the failure and the line or two above it.
4. **The versions.** Library, language, OS/arch — and the last version where it worked, if you found one.

Skip the essay. If your theory about the cause is short and useful, add one line at the end labeled as a guess. If it's long, it belongs in a follow-up comment after the maintainer has confirmed the bug.

## Other runtimes

Deno, Bun, Rust, Go, Docker (for OS-dependent bugs), a served-origin browser page, and repros that need a real HTTP server are in [references/templates.md](references/templates.md).

## Checklist

- [ ] One shell block; nothing to do between paste and failure
- [ ] Starts with `cd "$(mktemp -d)"` and leaves the user's cwd untouched
- [ ] Only assumes a package runner (`uv` / `pnpm` / `deno` / `bun`)
- [ ] Every dependency and the language version pinned exactly
- [ ] Exits non-zero, with expected and actual in the failure message
- [ ] Every line load-bearing — deleting any one stops the reproduction
- [ ] Comments only where they change the reader's understanding
- [ ] Verified against a known-good version or neighboring case
- [ ] Run twice in a fresh shell, same result
- [ ] The reported output is copied from a real run of the final block
