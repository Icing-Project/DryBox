"""Cross-platform path utilities for DryBox.

This module provides centralized path handling that:
1. Uses filesystem-first approach (avoids MultiplexedPath issues)
2. Supports Windows long paths (>260 chars)
3. Provides consistent project-relative directory resolution
"""
from __future__ import annotations

import sys
from pathlib import Path, PurePath
from typing import Optional

import platformdirs


# --- Project Root Detection ---
def _find_project_root() -> Path:
    """Find project root by looking for pyproject.toml or .git"""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return current.parents[1]  # Fallback: assume drybox/core/paths.py structure


PROJECT_ROOT = _find_project_root()
DRYBOX_PKG_DIR = Path(__file__).resolve().parent.parent  # drybox/

# --- Standard Directories ---
SCENARIOS_DIR = DRYBOX_PKG_DIR / "scenarios"
SCHEMA_DIR = DRYBOX_PKG_DIR / "schema"
ADAPTERS_DIR = PROJECT_ROOT / "adapters"


# --- User Directories (via platformdirs) ---
# NOTE: platformdirs added for potential future user settings/config features
# Currently all paths remain project-relative for drop-in compatibility

def get_user_data_dir() -> Path:
    """Get user data directory (for future use)."""
    return Path(platformdirs.user_data_dir("drybox", "Icing"))


def get_user_config_dir() -> Path:
    """Get user config directory (for future use)."""
    return Path(platformdirs.user_config_dir("drybox", "Icing"))


def get_runs_dir() -> Path:
    """Get runs output directory - always project-relative for compatibility."""
    return PROJECT_ROOT / "runs"


def _is_development_mode() -> bool:
    """Check if running in development/editable mode."""
    return (PROJECT_ROOT / "pyproject.toml").exists()


# --- Windows Long Path Support ---
def normalize_path(path: Path) -> Path:
    r"""Normalize path for Windows long path support.

    On Windows, paths longer than 260 characters require the \\?\ prefix.
    This function adds that prefix when needed.
    """
    if sys.platform != "win32":
        return path

    path_str = str(path.resolve())
    # Add long path prefix if needed (>260 chars) and not already present
    if len(path_str) > 260 and not path_str.startswith("\\\\?\\"):
        if path_str.startswith("\\\\"):
            # UNC path: \\server\share -> \\?\UNC\server\share
            path_str = "\\\\?\\UNC\\" + path_str[2:]
        else:
            path_str = "\\\\?\\" + path_str
        return Path(path_str)
    return path


# --- Safe Path Resolution ---
def resolve_resource_path(*parts: str, pkg_fallback: bool = True) -> Optional[Path]:
    """
    Resolve a resource path, filesystem-first approach.

    This avoids the MultiplexedPath issues with importlib.resources.files()
    in editable installs by checking the filesystem first.

    Args:
        *parts: Path components relative to drybox package (e.g., "scenarios", "test.yaml")
        pkg_fallback: Try importlib.resources if filesystem fails

    Returns:
        Resolved Path or None if not found
    """
    # 1. Try filesystem path first (works in dev and most installs)
    fs_path = DRYBOX_PKG_DIR.joinpath(*parts)
    if fs_path.exists():
        return normalize_path(fs_path)

    # 2. Fallback to importlib.resources for wheel/zipapp installs
    if pkg_fallback:
        try:
            from importlib import resources
            traversable = resources.files("drybox")
            for part in parts:
                traversable = traversable.joinpath(part)

            # Use as_file() context to get real path
            with resources.as_file(traversable) as real_path:
                if real_path.exists():
                    return normalize_path(Path(real_path))
        except (TypeError, FileNotFoundError, AttributeError):
            pass  # MultiplexedPath issues or missing resource

    return None


# --- Windows Reserved Name Check ---
WINDOWS_RESERVED = frozenset([
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
])


def is_valid_filename(name: str) -> bool:
    """Check if filename is valid on all platforms.

    Rejects Windows reserved names and invalid characters.
    """
    if not name:
        return False
    stem = PurePath(name).stem.upper()
    if stem in WINDOWS_RESERVED:
        return False
    # Check for invalid characters
    invalid_chars = '<>:"|?*' if sys.platform == "win32" else ""
    return not any(c in name for c in invalid_chars)


def safe_mkdir(path: Path, parents: bool = True, exist_ok: bool = True) -> Path:
    """Create directory with Windows long path support."""
    path = normalize_path(path)
    path.mkdir(parents=parents, exist_ok=exist_ok)
    return path
