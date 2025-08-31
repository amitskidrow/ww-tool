__all__ = ["__version__"]

# Derive version from installed package metadata to avoid drift with pyproject.toml
try:
    from importlib.metadata import version as _pkg_version
except Exception:  # pragma: no cover
    _pkg_version = None  # type: ignore

def _detect_version() -> str:
    try:
        if _pkg_version is None:
            return "0.0.0+dev"
        return _pkg_version("watchfiles-systemd")
    except Exception:
        # Fallback for editable/dev checkouts
        return "0.0.0+dev"

__version__ = _detect_version()
