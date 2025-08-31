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

force_clean_global() {
  echo "Force-cleaning existing ww installs (uv, pipx, pip, shims)"
  # uv tool uninstall
  if command -v uv >/dev/null 2>&1; then
    uv tool uninstall ww >/dev/null 2>&1 || true
  fi
  # pipx uninstall
  if command -v pipx >/dev/null 2>&1; then
    pipx uninstall watchfiles-systemd >/dev/null 2>&1 || true
  fi
  # user/system pip uninstall attempts
  python3 -m pip uninstall -y watchfiles-systemd >/dev/null 2>&1 || true
  pip3 uninstall -y watchfiles-systemd >/dev/null 2>&1 || true
  # remove shims
  rm -f "$HOME/.local/bin/ww" || true
}

canonical_git_spec() {
  # Convert a git remote URL into a pip/uv-compatible VCS spec
  # Input examples:
  #   https://github.com/user/repo.git
  #   git@github.com:user/repo.git
  # Output example:
  #   git+https://github.com/user/repo.git@main
  local url="$1"
  local branch="main"
  # If origin is SSH form, convert to https
  if [[ "$url" =~ ^git@([^:]+):(.+)$ ]]; then
    url="https://${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  fi
  # Ensure it starts with git+
  if [[ ! "$url" =~ ^git\+ ]]; then
    url="git+${url}"
  fi
  # Append @<branch> only if not present
  if [[ ! "$url" =~ @[^#]+$ && ! "$url" =~ @[^#]+# ]]; then
    url="${url}@${branch}"
  fi
  printf "%s" "$url"
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

  # Normalize to a VCS spec understood by uv/pip
  local spec
  spec=$(canonical_git_spec "$origin")

  # Quick smoke via uvx (ephemeral, not global)
  if command -v uvx >/dev/null 2>&1; then
    echo "Testing uvx tool run from: $origin"
    if UVX_OUT=$(uvx --from "$spec" ww --version 2>&1); then
      echo "uvx ww --version -> $UVX_OUT"
    else
      echo -e "uvx run failed:\n$UVX_OUT"
    fi
  else
    echo "uvx not found; skipping uvx check"
  fi

  # Preferred: global install via uv tool
  if command -v uv >/dev/null 2>&1; then
    echo "Installing globally via: uv tool install --force --from $spec watchfiles-systemd"
    if UV_TOOL_OUT=$(uv tool install --force --from "$spec" watchfiles-systemd 2>&1); then
      echo "$UV_TOOL_OUT" | sed -n '1,80p'
      echo "ww --version -> $(ww --version 2>&1 || true)"
    else
      echo -e "uv tool install failed, output follows:\n$UV_TOOL_OUT"
    fi
  elif command -v pipx >/dev/null 2>&1; then
    # Fallback: pipx with explicit spec+app to avoid VCS URL parsing issues
    echo "Installing globally via: pipx install --force --spec $spec watchfiles-systemd"
    if PIPX_OUT=$(pipx install --force --spec "$spec" watchfiles-systemd 2>&1); then
      echo "$PIPX_OUT" | sed -n '1,80p'
      if command -v ww >/dev/null 2>&1; then
        echo "ww --version -> $(ww --version 2>&1 || true)"
      else
        echo "ww command not found after pipx install"
      fi
    else
      echo -e "pipx install failed, output follows:\n$PIPX_OUT"
    fi
  else
    echo "Neither uv nor pipx found for global install. Consider installing Astral uv (preferred) or pipx."
  fi

  # Cleanup: remove older pipx-installed copy if present to avoid PATH conflicts
  if command -v pipx >/dev/null 2>&1; then
    if pipx list 2>/dev/null | grep -qE '^package +watchfiles-systemd[[:space:]]'; then
      # If pipx manages watchfiles-systemd but our current ww resolves elsewhere, remove the pipx one
      current_path=$(command -v ww || true)
      # pipx which may fail if not active; guard it
      pipx_path=$(pipx which ww 2>/dev/null || true)
      if [[ -n "$pipx_path" && -n "$current_path" && "$pipx_path" != "$current_path" ]]; then
        echo "Removing older pipx install to avoid shadowing: pipx uninstall watchfiles-systemd"
        pipx uninstall watchfiles-systemd || true
      fi
    fi
  fi

  # Show all ww candidates for diagnostics
  echo "ww on PATH (all candidates):"
  type -a ww 2>/dev/null || command -v ww || true

  # If an active virtualenv shadows ww, hint (or optionally clean)
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    if command -v ww >/dev/null 2>&1; then
      local ww_path
      ww_path=$(command -v ww)
      if [[ "$ww_path" == "$VIRTUAL_ENV"/bin/ww ]]; then
        echo "Note: Active virtualenv shadows global ww: $ww_path"
        echo "Deactivate venv or upgrade/uninstall ww in that venv to use the global install."
        if [[ "${WW_CLEAN_LOCAL_VENV:-}" == "1" ]]; then
          echo "WW_CLEAN_LOCAL_VENV=1 set: uninstalling watchfiles-systemd from current venv"
          "$VIRTUAL_ENV/bin/python" -m pip uninstall -y watchfiles-systemd || true
          rm -f "$VIRTUAL_ENV/bin/ww" || true
        fi
      fi
    fi
  fi
}

main() {
  bump_version
  commit_and_push
  if [[ "${WW_FORCE_CLEAN:-}" == "1" ]]; then
    force_clean_global || true
  fi
  install_remote
}

main "$@"
