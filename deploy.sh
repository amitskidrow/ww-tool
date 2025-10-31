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
  echo "[local mode] Skipping git commit/push (disabled)."
  return 0
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
  echo "[local mode] canonical_git_spec unused; keeping stub for compatibility."
  return 0
}

install_remote() {
  # LOCAL-ONLY INSTALL: no git, no remote. Prefer uv -> pipx -> user pip.
  echo "Installing locally from: $ROOT_DIR"

  if command -v uv >/dev/null 2>&1; then
    echo "Using: uv tool install --force --from $ROOT_DIR watchfiles-systemd"
    if UV_TOOL_OUT=$(uv tool install --force --from "$ROOT_DIR" watchfiles-systemd 2>&1); then
      echo "$UV_TOOL_OUT" | sed -n '1,80p'
      echo "ww --version -> $(ww --version 2>&1 || true)"
      return 0
    else
      echo -e "uv tool install failed, output follows:\n$UV_TOOL_OUT"
    fi
  fi

  if command -v pipx >/dev/null 2>&1; then
    echo "Using: pipx install --force $ROOT_DIR"
    if PIPX_OUT=$(pipx install --force "$ROOT_DIR" 2>&1); then
      echo "$PIPX_OUT" | sed -n '1,80p'
      if command -v ww >/dev/null 2>&1; then
        echo "ww --version -> $(ww --version 2>&1 || true)"
      else
        echo "ww command not found after pipx install"
      fi
      return 0
    else
      echo -e "pipx install failed, output follows:\n$PIPX_OUT"
    fi
  fi

  echo "Falling back to user-site pip install"
  if python3 -m pip install --user --upgrade "$ROOT_DIR"; then
    :
  else
    pip3 install --user --upgrade "$ROOT_DIR" || true
  fi
  if command -v ww >/dev/null 2>&1; then
    echo "ww --version -> $(ww --version 2>&1 || true)"
  else
    echo "Note: ww may be in ~/.local/bin; ensure it's on PATH"
  fi
}

main() {
  bump_version
  if [[ "${WW_FORCE_CLEAN:-}" == "1" ]]; then
    force_clean_global || true
  fi
  install_remote
}

main "$@"
