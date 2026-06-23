#!/bin/bash
# validate-scope.sh - Validate a commit scope against this repo's scope rules
#
# Usage: ./validate-scope.sh <scope>
#        ./validate-scope.sh "scope: subject line"   # a full subject also works
#
# Rules (https://scopedcommits.com/):
#   - Monorepo:      scope MUST be a workspace package name OR a narrow global
#                    (scripts, ci, docs). `treewide` is always allowed.
#   - Single-package: scope may be any single token with no spaces OR a narrow
#                    global. `treewide` is always allowed.
#
# Exit codes: 0 = valid, 1 = invalid scope, 2 = usage error.

set -euo pipefail

NARROW_GLOBALS=("scripts" "ci" "docs" "treewide")

usage() {
    echo "Usage: $0 <scope>" >&2
    echo "       $0 \"scope: subject\"" >&2
}

if [ "$#" -lt 1 ] || [ -z "${1:-}" ]; then
    usage
    exit 2
fi

# Accept either a bare scope or a full "scope: subject"; take the part before ':'
RAW="$1"
SCOPE="${RAW%%:*}"
# Strip a trailing breaking-change marker and surrounding whitespace.
SCOPE="${SCOPE%!}"
SCOPE="$(echo "$SCOPE" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"

if [ -z "$SCOPE" ]; then
    echo "ERROR: empty scope" >&2
    exit 1
fi

# Find the repo root so detection works from any subdirectory.
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

is_narrow_global() {
    local candidate="$1"
    for g in "${NARROW_GLOBALS[@]}"; do
        if [ "$candidate" = "$g" ]; then
            return 0
        fi
    done
    return 1
}

has_spaces() {
    case "$1" in
        *[[:space:]]*) return 0 ;;
        *) return 1 ;;
    esac
}

# --- Monorepo detection ----------------------------------------------------
# A repo is treated as a monorepo if it declares a workspace or has a packages/
# directory or multiple package manifests under src/*.
is_monorepo() {
    [ -f "$REPO_ROOT/pnpm-workspace.yaml" ] && return 0
    if [ -f "$REPO_ROOT/package.json" ] && grep -q '"workspaces"' "$REPO_ROOT/package.json" 2>/dev/null; then
        return 0
    fi
    if [ -f "$REPO_ROOT/Cargo.toml" ] && grep -qE '^\[workspace\]' "$REPO_ROOT/Cargo.toml" 2>/dev/null; then
        return 0
    fi
    if [ -d "$REPO_ROOT/packages" ]; then
        return 0
    fi
    # Multiple package manifests under src/* also implies a monorepo.
    local count
    count=$(find "$REPO_ROOT/src" -maxdepth 2 \
        \( -name package.json -o -name Cargo.toml -o -name pyproject.toml \) \
        2>/dev/null | wc -l | tr -d ' ')
    [ "${count:-0}" -ge 2 ]
}

# --- Enumerate workspace package names -------------------------------------
list_packages() {
    {
        # JS/TS packages: name field of each package.json (excluding root + deps).
        find "$REPO_ROOT" \
            -path "$REPO_ROOT/node_modules" -prune -o \
            -name package.json -not -path "$REPO_ROOT/package.json" -print 2>/dev/null \
            | while read -r pkg; do
                grep -m1 '"name"' "$pkg" 2>/dev/null \
                    | sed -E 's/.*"name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/' \
                    | sed -E 's#^@[^/]+/##'  # drop npm scope prefix
            done

        # Rust crates: package.name in each Cargo.toml (excluding the root file).
        find "$REPO_ROOT" \
            -path "$REPO_ROOT/target" -prune -o \
            -name Cargo.toml -not -path "$REPO_ROOT/Cargo.toml" -print 2>/dev/null \
            | while read -r crate; do
                awk '/^\[package\]/{p=1; next} /^\[/{p=0} p && /^[[:space:]]*name[[:space:]]*=/{gsub(/.*=[[:space:]]*"|".*/, ""); print; exit}' "$crate"
            done

        # Python projects: project.name in each pyproject.toml.
        find "$REPO_ROOT" \
            -name pyproject.toml -not -path "$REPO_ROOT/pyproject.toml" -print 2>/dev/null \
            | while read -r proj; do
                awk '/^\[project\]/{p=1; next} /^\[/{p=0} p && /^[[:space:]]*name[[:space:]]*=/{gsub(/.*=[[:space:]]*"|".*/, ""); print; exit}' "$proj"
            done

        # Directory names directly under packages/ as a fallback.
        if [ -d "$REPO_ROOT/packages" ]; then
            find "$REPO_ROOT/packages" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; 2>/dev/null
        fi
    } | sort -u | grep -v '^$'
}

if is_monorepo; then
    if is_narrow_global "$SCOPE"; then
        echo "OK: '$SCOPE' is an allowed global scope."
        exit 0
    fi

    PACKAGES="$(list_packages)"
    if [ -n "$PACKAGES" ] && echo "$PACKAGES" | grep -Fxq "$SCOPE"; then
        echo "OK: '$SCOPE' is a workspace package."
        exit 0
    fi

    echo "ERROR: in a monorepo the scope must be a package name or one of: ${NARROW_GLOBALS[*]}" >&2
    if [ -n "$PACKAGES" ]; then
        echo "Known packages:" >&2
        echo "$PACKAGES" | sed 's/^/  - /' >&2
    fi
    exit 1
fi

# --- Single-package repo ---------------------------------------------------
# The scope must be a directory or an extensionless file path that locates the
# change in the tree (e.g. `utils`, `auth`, `utils/jwt`, `components/file-picker`)
# or a narrow global. Never a bare filename with an extension.
if is_narrow_global "$SCOPE"; then
    echo "OK: '$SCOPE' is an allowed global scope."
    exit 0
fi

if has_spaces "$SCOPE"; then
    echo "ERROR: scope '$SCOPE' contains spaces; use a directory or extensionless file path (e.g. 'utils/jwt')." >&2
    exit 1
fi

case "$SCOPE" in
    .*|*/) echo "ERROR: scope '$SCOPE' must be a clean path; no leading dot or trailing slash." >&2; exit 1 ;;
    */.*) echo "ERROR: scope '$SCOPE' must not contain a dotfile segment." >&2; exit 1 ;;
esac

# Reject file extensions: the scope must be extensionless. A '.' in the last
# path segment indicates an extension (e.g. 'utils/jwt.ts').
LAST_SEGMENT="${SCOPE##*/}"
if [ "$LAST_SEGMENT" != "${LAST_SEGMENT%.*}" ]; then
    echo "ERROR: scope '$SCOPE' includes a file extension; drop it (e.g. use 'utils/jwt', not 'utils/jwt.ts')." >&2
    exit 1
fi

echo "OK: '$SCOPE' is a valid directory/path scope."
exit 0
