#!/usr/bin/env bash
set -euo pipefail

# Deploy branch can be overridden via $DEPLOY_BRANCH
# Migration default branch for the new architecture workstream
DEPLOY_BRANCH="${DEPLOY_BRANCH:-migration/new-arch}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

timestamp() {
  date +"%Y-%m-%d %H:%M:%S"
}

# Bump patch version in pyproject.toml and we_dash/__init__.py
bump_version() {
  local pyproject="$ROOT_DIR/pyproject.toml"
  local init_py="$ROOT_DIR/we_dash/__init__.py"

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

  # Update pyproject.toml
  sed -i -E 's/^(version = ")[0-9]+\.[0-9]+\.[0-9]+(")/\1'"${next_version}"'\2/' "$pyproject"

  # Update package __version__ if present
  if [[ -f "$init_py" ]]; then
    sed -i -E 's/^(__version__ = ")[0-9]+\.[0-9]+\.[0-9]+(")/\1'"${next_version}"'\2/' "$init_py"
  fi

  echo "Bumped version: ${current} -> ${next_version}"
}

commit_and_push() {
  local ts
  ts=$(timestamp)
  git -C "$ROOT_DIR" add -A
  if ! git -C "$ROOT_DIR" diff --staged --quiet; then
    local v
    v=$(sed -nE 's/^version = "([^"]+)"/\1/p' "$ROOT_DIR/pyproject.toml" | head -n1 || true)
    if [[ -n "$v" ]]; then
      git -C "$ROOT_DIR" commit -m "chore(release): v${v} (${ts})"
    else
      git -C "$ROOT_DIR" commit -m "Auto deploy: ${ts}"
    fi
    echo "Committed changes"
  else
    echo "No changes to commit"
  fi
  git -C "$ROOT_DIR" push -u origin "$DEPLOY_BRANCH" || true
  echo "Pushed to GitHub"
}

# Convert origin URL to a PEP 508 VCS spec suitable for uvx/pipx
origin_spec() {
  local origin
  origin=$(git -C "$ROOT_DIR" remote get-url origin 2>/dev/null || echo "")
  if [[ -z "$origin" ]]; then
    echo ""; return 0
  fi
  local https
  if [[ "$origin" =~ ^git@github.com:(.*)\.git$ ]]; then
    https="https://github.com/${BASH_REMATCH[1]}.git"
  elif [[ "$origin" =~ ^ssh://git@github.com/(.*)\.git$ ]]; then
    https="https://github.com/${BASH_REMATCH[1]}.git"
  else
    https="$origin"
  fi
  if [[ "$https" != git+* ]]; then
    https="git+${https}"
  fi
  # default to @${DEPLOY_BRANCH} ref
  if [[ "$https" != *"@"* ]]; then
    https="${https}@${DEPLOY_BRANCH}"
  fi
  echo "$https"
}

install_remote() {
  echo "Waiting for remote to be ready..."
  sleep 15

  local spec
  spec=$(origin_spec)

  # Ephemeral validation via uvx if present
  if command -v uvx >/dev/null 2>&1; then
    echo "Checking via uvx from $spec"
    set +e
    uvx --from "$spec" we-dash --help >/tmp/we_dash_help.txt 2>&1
    local rc1=$?
    uvx --from "$spec" python -c 'import we_dash; print(we_dash.__version__)' >/tmp/we_dash_ver.txt 2>&1
    set -e
    echo "we-dash --help rc=$rc1"
    if [[ -s /tmp/we_dash_ver.txt ]]; then
      echo "Installed version: $(cat /tmp/we_dash_ver.txt)"
    else
      echo "Could not determine version via uvx"
    fi
  fi

  # Prefer global install with uv tool so 'which we-dash' resolves
  if command -v uv >/dev/null 2>&1; then
    echo "Installing globally via: uv tool install --force --from $spec we-dash"
    if UV_TOOL_OUT=$(uv tool install --force --from "$spec" we-dash 2>&1); then
      echo "$UV_TOOL_OUT" | sed -n '1,80p'
      echo "we-dash --version -> $(we-dash --help >/dev/null 2>&1 && python -c 'import we_dash, sys; sys.stdout.write(getattr(we_dash, "__version__", "unknown"))' 2>/dev/null || echo unknown)"
      echo "which we-dash -> $(command -v we-dash || echo not found)"
      return 0
    else
      echo -e "uv tool install failed, output follows:\n$UV_TOOL_OUT"
    fi
  fi

  # Fallback to pipx if available
  if command -v pipx >/dev/null 2>&1; then
    echo "Installing globally via: pipx install --force --spec $spec we-dash (or legacy syntax)"
    if PIPX_OUT=$(pipx install --force --spec "$spec" we-dash 2>&1); then
      echo "$PIPX_OUT" | sed -n '1,80p'
      echo "which we-dash -> $(command -v we-dash || echo not found)"
      echo "we-dash --version -> $(we-dash --help >/dev/null 2>&1 && python -c 'import we_dash, sys; sys.stdout.write(getattr(we_dash, "__version__", "unknown"))' 2>/dev/null || echo unknown)"
      return 0
    else
      echo "pipx --spec not supported; trying: pipx install --force $spec"
      if PIPX_OUT2=$(pipx install --force "$spec" 2>&1); then
        echo "$PIPX_OUT2" | sed -n '1,80p'
        echo "which we-dash -> $(command -v we-dash || echo not found)"
        echo "we-dash --version -> $(we-dash --help >/dev/null 2>&1 && python -c 'import we_dash, sys; sys.stdout.write(getattr(we_dash, "__version__", "unknown"))' 2>/dev/null || echo unknown)"
        return 0
      else
        echo -e "pipx install failed, output follows:\n$PIPX_OUT\n--- legacy attempt ---\n$PIPX_OUT2"
      fi
    fi
  fi

  # Final fallback: install from local checkout
  if command -v uv >/dev/null 2>&1; then
    echo "Falling back to local install via uv tool"
    if UV_TOOL_OUT2=$(uv tool install --force --from . we-dash 2>&1); then
      echo "$UV_TOOL_OUT2" | sed -n '1,80p'
      echo "which we-dash -> $(command -v we-dash || echo not found)"
      echo "we-dash --version -> $(we-dash --help >/dev/null 2>&1 && python -c 'import we_dash, sys; sys.stdout.write(getattr(we_dash, "__version__", "unknown"))' 2>/dev/null || echo unknown)"
      return 0
    fi
  fi
  if command -v pipx >/dev/null 2>&1; then
    echo "Falling back to local install via pipx"
    if PIPX_OUT3=$(pipx install --force . 2>&1); then
      echo "$PIPX_OUT3" | sed -n '1,80p'
      echo "which we-dash -> $(command -v we-dash || echo not found)"
      echo "we-dash --version -> $(we-dash --help >/dev/null 2>&1 && python -c 'import we_dash, sys; sys.stdout.write(getattr(we_dash, "__version__", "unknown"))' 2>/dev/null || echo unknown)"
      return 0
    fi
  fi
  echo "No usable installer or all installs failed; performed only ephemeral uvx check"
}

main() {
  bump_version
  commit_and_push
  install_remote
}

main "$@"
