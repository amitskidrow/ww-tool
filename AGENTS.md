# Repository Guidelines

## Project Structure & Module Organization
- `src/watchfiles_systemd/`: package code
  - `cli.py`: Typer CLI (commands: `ps`, `pid`, `logs`, `restart*`, `stop*`, `rm*`, `doctor`, `dash`, `main`)
  - `systemd_bus.py`: systemd D‑Bus helpers
  - `util.py`: path resolution, slugging, watchfiles command builder
  - `entry.py`: `ww` script entrypoint
  - `__init__.py`: version detection
  - `dash/`: internal WW dashboard (Textual) with ww‑specific discovery and commands
- `test/`: simple smoke example (`test.py`) for local runs
- `ss_smoketest/`: another small runnable example
- `pyproject.toml`: packaging (setuptools), script entry `ww`
- `prd.md`: product/behavior spec; `deploy.sh`: release helper

## Build, Test, and Development Commands
- Create env: `uv venv` (or `python -m venv .venv`)
- Install editable: `uv pip install -e .`
- Run CLI: `.venv/bin/ww --help` or `ww --help`
- Local smoke tests:
  - `ww ss_smoketest` (directory mode)
  - `ww test/test.py` (file mode)
- Dashboard:
  - `ww dash` opens Textual UI over ww units (no project sentinels)
  - Textual is installed by default. Optional extras for embedded terminal backends:
    - `uv tool install --from <REPO_URL> ww[dash-terminal]` and/or `ww[dash-tmux]`
    - Or with pip: `pip install watchfiles-systemd[dash-terminal]` / `[dash-tmux]`
- From Git without install: `uvx --from <REPO_URL> ww --help`

## Coding Style & Naming Conventions
- Python ≥ 3.9, PEP 8, 4‑space indent, type hints required for new code.
- Functions small and pure where practical; docstrings for public helpers.
- Module/file names: `snake_case.py`. CLI command names are short, lowercase.
- Unit names: derived by `to_slug()` and prefixed by `ww-…`. Allowed chars `[a-z0-9._-]`; example: `api-server` → `ww-api-server.service`.

## Testing Guidelines
- No formal test framework configured yet. Use the provided smoke examples to validate flows.
- If adding tests, prefer `pytest` with files named `test_*.py` under `test/`. Keep tests fast and isolate systemd calls with fakes where possible.
- Validate key paths: slugging, path resolution, and exec construction in `util.py`.

## Commit & Pull Request Guidelines
- Commit style: conventional-commit flavored. Example: `feat(cli): add doctor command`. The release script uses `chore(release): vX.Y.Z`.
- PRs should include:
  - What/why summary and linked issues
  - How to test (exact commands, expected output)
  - Screenshots or `journalctl` excerpts when relevant
  - Notes on backward compatibility and docs updates

## Security & Configuration Tips
- Requires systemd user session, D‑Bus, and journald. For long‑running after logout: `loginctl enable-linger $USER`.
- External tools: `uvx` to run `watchfiles` on demand. Env knobs: `WW_IGNORE` (extra ignore paths, comma‑separated), `WW_WF_VERSION` (pin watchfiles version).
