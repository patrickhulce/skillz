---
name: python-script
description: Guidance for writing one-off / standalone Python scripts. Use when creating a quick script, throwaway utility, automation snippet, or any single-file Python program. Scripts must be self-contained, run with uv and an explicit Python version, and declare dependencies via a PEP 723 inline metadata header with exact version pins.
disable-model-invocation: true
---

# Writing One-Off Python Scripts

One-off scripts must be **self-contained and reproducible**. Anyone should be able to run the script with a single command, no `pip install`, no virtualenv setup, no "works on my machine".

Two non-negotiable rules:

1. **Always run with `uv` and an explicit Python version.**
2. **Always include the PEP 723 inline `uv` header** declaring every dependency with an exact version pin.

## Required script header

Every script starts with a PEP 723 inline metadata block (the "uv header"). Pin `requires-python` to a specific minor version and pin every dependency with `==`.

```python
# /// script
# requires-python = "==3.12.*"
# dependencies = [
#   "requests==2.32.3",
#   "rich==13.9.4",
# ]
# ///
"""Short description of what this script does."""

import requests
from rich import print

def main() -> None:
    resp = requests.get("https://httpbin.org/get", timeout=10)
    print(resp.json())

if __name__ == "__main__":
    main()
```

If the script has **no** third-party dependencies, still include the header with an empty list so the run command and Python version stay explicit:

```python
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
```

## Running the script

Always pass `--python` so the version is explicit and reproducible, even though `requires-python` is set:

```bash
uv run --python 3.12 script.py
```

Make it directly executable with a uv shebang for repeated use:

```python
#!/usr/bin/env -S uv run --python 3.12 --script
# /// script
# requires-python = "==3.12.*"
# dependencies = ["requests==2.32.3"]
# ///
```

```bash
chmod +x script.py
./script.py
```

## Dependency rules

- **Pin exact versions** (`requests==2.32.3`), never unpinned (`requests`) or ranges (`requests>=2`). One-off scripts should be frozen in time so they keep working.
- To resolve the current latest version of a package to pin, run `uv pip index versions <package>` (or check PyPI) and use the top stable release.
- Add a new dependency to an existing script with:

```bash
uv add --script script.py "httpx==0.28.1"
```

This rewrites the header with the pinned version for you.

## Checklist

Before considering a one-off script done:

- [ ] Has the `# /// script` ... `# ///` PEP 723 header
- [ ] `requires-python` pins a specific minor version (e.g. `==3.12.*`)
- [ ] Every dependency pinned with `==` to an exact version (or an empty list)
- [ ] Runs cleanly via `uv run --python 3.12 script.py`
- [ ] Self-contained in a single file with no external setup steps
