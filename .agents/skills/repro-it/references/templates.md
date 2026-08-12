# Repro templates by runtime

Scaffolding for runtimes beyond the three in `SKILL.md`. Same contract everywhere: one shell block, its own temp directory, pinned versions, non-zero exit.

## Deno

No `package.json`, no install step — `npm:` specifiers carry the pin.

```bash
cd "$(mktemp -d)" && cat > repro.ts <<'EOF'
import _ from "npm:lodash@4.17.21";

const out = _.merge({ a: [1, 2] }, { a: [3] });
console.log(out);
if (JSON.stringify(out.a) !== "[3]") {
  throw new Error(`expected [3], got ${JSON.stringify(out.a)}`);
}
EOF
deno run -A repro.ts
```

Use `deno run` with the narrowest flags the bug needs (`--allow-net=127.0.0.1` rather than `-A`) when permissions are part of the story.

## Bun

```bash
cd "$(mktemp -d)" && bun init -y >/dev/null && bun add lodash@4.17.21 >/dev/null && cat > repro.ts <<'EOF'
import assert from "node:assert/strict";
import _ from "lodash";

const out = _.merge({ a: [1, 2] }, { a: [3] });
console.log(out);
assert.deepEqual(out.a, [3], "expected replacement, got element-wise merge");
EOF
bun run repro.ts
```

Use `node:assert/strict` rather than `bun:test`'s `expect` unless the bug is in the test runner — `bun run` is a plainer surface than `bun test`, so it keeps the repro about the library.

## Browser with a real origin

`page.set_content()` runs on `about:blank`, which breaks ES module imports, CORS, cookies, and service workers. When the bug needs an origin, serve a temp directory on an ephemeral port from inside the script.

```bash
cd "$(mktemp -d)" && cat > index.html <<'EOF'
<div id="out">pending</div>
<script type="module">
  import { format } from "./mod.js";
  document.getElementById("out").textContent = format(1.5);
</script>
EOF
cat > mod.js <<'EOF'
export const format = (n) => n.toFixed(0);
EOF
cat > repro.py <<'EOF'
# /// script
# requires-python = "==3.12.*"
# dependencies = ["playwright==1.49.1"]
# ///
import functools, http.server, socketserver, threading
from playwright.sync_api import sync_playwright

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=".")
srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(url)
    text = page.locator("#out").inner_text()
    browser.close()

print("rendered:", text)
assert text == "2", f"expected '2', got {text!r}"
EOF
uv run --python 3.12 --with playwright==1.49.1 playwright install chromium
uv run --python 3.12 repro.py
```

Port `0` lets the OS pick a free port, so the repro can't collide with whatever the reader already has running.

Useful additions when the bug is visual or console-only:

```python
page.on("console", lambda m: print("console:", m.type, m.text))
page.on("pageerror", lambda e: print("pageerror:", e))
page.screenshot(path="repro.png")  # attach to the issue
```

To show a bug is browser-specific, loop over engines and assert per engine:

```python
for name in ("chromium", "firefox", "webkit"):
    browser = getattr(p, name).launch()
    ...
    print(name, result)
```

That variant needs `playwright install chromium firefox webkit` in the block instead of just `chromium`.

## Client/server in one script

For bugs that need a real HTTP round trip (framework routing, middleware, serialization).

```bash
cd "$(mktemp -d)" && cat > repro.py <<'EOF'
# /// script
# requires-python = "==3.12.*"
# dependencies = ["fastapi==0.115.6", "httpx==0.28.1"]
# ///
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()

@app.get("/items/{item_id}")
def read(item_id: int) -> dict:
    return {"id": item_id}

r = TestClient(app).get("/items/007")
print(r.status_code, r.json())
assert r.json()["id"] == "007", f"expected '007', got {r.json()['id']!r}"
EOF
uv run --python 3.12 repro.py
```

An in-process test client beats spawning a server: no ports, no startup race, no cleanup. Reach for a real server only when the bug lives in the transport.

## Rust

```bash
cd "$(mktemp -d)" && cargo new repro --quiet && cd repro && cargo add serde_json@1.0.133 --quiet && cat > src/main.rs <<'EOF'
fn main() {
    let v: serde_json::Value = serde_json::from_str(r#"{"b": 1, "a": 2}"#).unwrap();
    let out = serde_json::to_string(&v).unwrap();
    println!("{out}");
    assert_eq!(out, r#"{"b":1,"a":2}"#, "expected insertion order, got sorted keys");
}
EOF
cargo run --quiet
```

Pin the toolchain when the bug is version-specific by writing this into the project directory before `cargo run`:

```bash
printf '[toolchain]\nchannel = "1.83.0"\n' > rust-toolchain.toml
```

## Go

```bash
cd "$(mktemp -d)" && go mod init repro >/dev/null && cat > main.go <<'EOF'
package main

import (
	"encoding/json"
	"fmt"
)

func main() {
	var m map[string]any
	json.Unmarshal([]byte(`{"n": 1}`), &m)
	fmt.Printf("%T\n", m["n"])
	if _, ok := m["n"].(int); !ok {
		panic(fmt.Sprintf("expected int, got %T", m["n"]))
	}
}
EOF
go run main.go
```

Add `go get example.com/pkg@v1.2.3` between the `go mod init` and the heredoc for third-party dependencies.

## Docker — OS, libc, and architecture bugs

Reach for this only when the bug depends on the environment rather than the code: glibc vs musl, a specific base image, CPU architecture, locale.

```bash
cd "$(mktemp -d)" && cat > repro.py <<'EOF'
import platform
print(platform.platform(), platform.libc_ver())
assert platform.libc_ver()[0] == "glibc", f"expected glibc, got {platform.libc_ver()}"
EOF
docker run --rm -v "$PWD:/w" -w /w python:3.12.8-alpine python repro.py
```

Pin the image by exact tag (`python:3.12.8-alpine`, never `python:3`), and add `--platform linux/amd64` when the architecture is the point. Swapping only the image tag between two otherwise identical runs is the environment-level version of the A/B check.

## Existing repository, pinned to a commit

When the bug genuinely needs a whole project, the repro is still one block — clone at a fixed ref rather than describing setup steps.

```bash
cd "$(mktemp -d)" && git clone --depth 1 --branch v2.3.0 https://github.com/org/proj . >/dev/null 2>&1 && uv sync --quiet && uv run pytest tests/test_thing.py::test_case -x
```

Treat this as a last resort. Maintainers triage a ten-line script far faster than a clone, and cloning reintroduces every assumption the temp-directory approach removed.

## Test-runner-shaped repro

Some maintainers prefer a failing test they can drop into their suite. Keep it a single self-installing file anyway:

```bash
cd "$(mktemp -d)" && cat > test_repro.py <<'EOF'
from pydantic import BaseModel

class M(BaseModel):
    x: int

def test_str_passthrough():
    assert M(x="3").x == "3"
EOF
uv run --python 3.12 --with pytest==8.3.4 --with pydantic==2.9.2 pytest test_repro.py -q
```

There is no PEP 723 header here: `uv run` only reads that header when the target is the script itself, and here the target is the `pytest` command. Every dependency has to move onto the command line as a `--with` flag instead.

Offer this in addition to the plain script, never instead of it — the plain script is what gets pasted into an issue.
