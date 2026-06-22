# myplaceholder-project

Polyglot monorepo: Rust core library with Python and Node.js bindings.

## Prerequisites

- Rust (stable)
- [uv](https://docs.astral.sh/uv/)
- [pnpm](https://pnpm.io/) 9+
- Node.js 22+

## Layout

```
src/
├── rust-myplaceholder-project/     # Core Rust library
├── python-myplaceholder-project/   # PyO3 + maturin bindings
└── node-myplaceholder-project/     # napi-rs + TypeScript bindings
```

## Commands

```bash
make              # build, lint, typecheck, test
make build        # build all targets
make test         # run all tests
```

## Usage

```rust
// Rust
myplaceholder_rust_crate::echo(b"hello");
```

```python
from myplaceholder_project import echo
echo(b"hello")
```

```typescript
import { echo } from "myplaceholder-npm-pkg";
echo(Buffer.from("hello"));
```

Replace the `echo` stub in `src/rust-myplaceholder-project/src/lib.rs` with your real API; keep bindings thin.
