#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

# Optionally bump patch version in pyproject.toml if present
bump_version() {
  local pyproject="$ROOT_DIR/pyproject.toml"
  if [[ ! -f "$pyproject" ]]; then
    echo "pyproject.toml not found; skipping version bump"
    return 0
  fi

  local current
  current=$(sed -nE 's/^version = "([^"]+)"/\1/p' "$pyproject" | head -n1)
  if [[ -z "$current" ]]; then
    echo "Could not determine current version from pyproject.toml; skipping version bump"
    return 0
  fi

  IFS='.' read -r MAJOR MINOR PATCH <<< "$current"
  if [[ -z "${MAJOR:-}" || -z "${MINOR:-}" || -z "${PATCH:-}" ]]; then
    echo "Unexpected version format: $current; skipping version bump"
    return 0
  fi

  local next_patch=$((PATCH + 1))
  local next_version="${MAJOR}.${MINOR}.${next_patch}"

  # Update pyproject.toml (replace only the numeric part)
  sed -i -E 's/^(version = ")[0-9]+\.[0-9]+\.[0-9]+(")/\1'"${next_version}"'\2/' "$pyproject"
  echo "Bumped version: ${current} -> ${next_version}"
}

commit_and_push() {
  local ts
  ts=$(timestamp)
  git -C "$ROOT_DIR" add -A
  if ! git -C "$ROOT_DIR" diff --staged --quiet; then
    # Try to extract version for a nicer message
    local v
    v=$(sed -nE 's/^version = "([^"]+)"/\1/p' "$ROOT_DIR/pyproject.toml" | head -n1 || true)
    if [[ -n "${v:-}" ]]; then
      git -C "$ROOT_DIR" commit -m "chore(release): v${v} (${ts})"
    else
      git -C "$ROOT_DIR" commit -m "Auto deploy: ${ts}"
    fi
    echo "Committed changes"
  else
    echo "No changes to commit"
  fi

  git -C "$ROOT_DIR" push origin main
  echo "Pushed to GitHub"
}

install_remote() {
  # Determine origin URL for this repo
  local origin
  origin=$(git -C "$ROOT_DIR" remote get-url origin 2>/dev/null || true)
  if [[ -z "${origin:-}" ]]; then
    echo "No git origin configured; skipping remote install checks"
    return 0
  fi

  echo "Waiting for remote to update..."
  sleep 15

  # Try uvx tool-run from Git
  if command -v uvx >/dev/null 2>&1; then
    echo "Testing uvx tool run from: $origin"
    if UVX_OUT=$(uvx --from "$origin" ww --version 2>&1); then
      echo "uvx ww --version -> $UVX_OUT"
    else
      echo "uvx run failed:\n$UVX_OUT"
    fi
  else
    echo "uvx not found; skipping uvx check"
  fi

  # Try pipx global install from Git
  if command -v pipx >/dev/null 2>&1; then
    echo "Testing pipx install from: $origin"
    if PIPX_OUT=$(pipx install --force "$origin" 2>&1); then
      echo "$PIPX_OUT" | sed -n '1,50p'
      if command -v ww >/dev/null 2>&1; then
        echo "ww --version -> $(ww --version 2>&1 || true)"
      else
        echo "ww command not found after pipx install"
      fi
    else
      echo "pipx install failed"
    fi
  else
    echo "pipx not found; skipping pipx check"
  fi
}

main() {
  bump_version
  commit_and_push
  install_remote
}

main "$@"

