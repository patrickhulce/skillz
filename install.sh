#!/usr/bin/env bash
# install.sh - skillz install bootstrap
#
# Validates the host environment (Python 3.11 or uv), then downloads
# src/skillz/install.py from GitHub and hands off to it.
#
# Usage:
#   ./install.sh [--ref REF] [--branch NAME] [--target {repo,user}] [--yes] [--dry-run]
#   curl -fsSL https://raw.githubusercontent.com/patrickhulce/skillz/main/install.sh | bash
#
# Env overrides:
#   SKILLZ_REPO   - owner/repo on GitHub (default: patrickhulce/skillz)

set -euo pipefail

CLI_REF=""
CLI_BRANCH=""
REMAINING=()
while [ $# -gt 0 ]; do
  case "$1" in
    --ref)
      [ $# -ge 2 ] || { printf '%s missing value for --ref\n' "[FAIL]" >&2; exit 1; }
      CLI_REF="$2"
      shift 2
      ;;
    --branch)
      [ $# -ge 2 ] || { printf '%s missing value for --branch\n' "[FAIL]" >&2; exit 1; }
      CLI_BRANCH="$2"
      shift 2
      ;;
    *)
      REMAINING+=("$1")
      shift
      ;;
  esac
done
set -- "${REMAINING[@]}"

REPO="${SKILLZ_REPO:-patrickhulce/skillz}"
if [ -n "${CLI_BRANCH}" ]; then
  REF="refs/heads/${CLI_BRANCH}"
elif [ -n "${CLI_REF}" ]; then
  REF="${CLI_REF}"
elif [ -n "${SKILLZ_BRANCH:-}" ]; then
  REF="refs/heads/${SKILLZ_BRANCH}"
elif [ -n "${SKILLZ_REF:-}" ]; then
  REF="${SKILLZ_REF}"
else
  REF="refs/heads/main"
fi

if [[ "${REF}" == refs/heads/* ]]; then
  REF_PATH="${REF#refs/heads/}"
elif [[ "${REF}" == refs/tags/* ]]; then
  REF_PATH="${REF#refs/tags/}"
else
  REF_PATH="${REF}"
fi
INSTALLER_URL="https://raw.githubusercontent.com/${REPO}/${REF_PATH}/src/skillz/install.py"

ok()   { printf '\033[32m[OK]\033[0m   %s\n' "$*"; }
fail() { printf '\033[31m[FAIL]\033[0m %s\n' "$*" >&2; }
info() { printf '\033[36m[..]\033[0m   %s\n' "$*"; }

info "skillz installer (ref=${REF}, repo=${REPO})"

PY_RUNNER=""
PY_RUNNER_DESC=""
if command -v python3.11 >/dev/null 2>&1; then
    PY_RUNNER="python3.11"
    PY_RUNNER_DESC="$(command -v python3.11)"
elif command -v uv >/dev/null 2>&1; then
    PY_RUNNER="uv"
    PY_RUNNER_DESC="uv ($(command -v uv)) running --python 3.11"
else
    fail "neither python3.11 nor uv is on PATH"
    cat >&2 <<'EOF'
       install one of:
         - Python 3.11:   brew install python@3.11
         - uv:            curl -LsSf https://astral.sh/uv/install.sh | sh
EOF
    exit 1
fi
ok "python runner: ${PY_RUNNER_DESC}"

TMP="$(mktemp -t skillz-install.XXXXXX.py)"
trap 'rm -f "$TMP"' EXIT

info "downloading installer from ${INSTALLER_URL}"
if ! curl -fsSL "$INSTALLER_URL" -o "$TMP"; then
    fail "could not download installer from ${INSTALLER_URL}"
    exit 1
fi

if [ ! -s "$TMP" ]; then
    fail "downloaded installer is empty"
    exit 1
fi
ok "downloaded installer ($(wc -c <"$TMP" | tr -d ' ') bytes)"

export SKILLZ_REF="$REF"
export SKILLZ_REPO="$REPO"

info "handing off to Python installer"
case "$PY_RUNNER" in
    python3.11)
        exec python3.11 "$TMP" "$@"
        ;;
    uv)
        exec uv run --python 3.11 --no-project "$TMP" "$@"
        ;;
esac
