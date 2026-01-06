from __future__ import annotations

import os
import inspect
from dataclasses import dataclass
from importlib import import_module, metadata, util as importlib_util
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ADAPTERS_DIR = PROJECT_ROOT / "adapters"
ENTRYPOINT_GROUP = "drybox.adapters"
ENTRYPOINT_PREFIXES = ("entrypoint:", "pkg:")


@dataclass(frozen=True)
class AdapterInfo:
    """Descriptor for an adapter endpoint that DryBox can load."""

    identifier: str  # persisted in scenarios (e.g. "nade_adapter.py" or "entrypoint:nade")
    display_name: str  # shown in GUI combo boxes
    spec: str  # fully qualified spec passed to the runner (file path or entrypoint)
    source: Literal["file", "entrypoint"]
    metadata: Dict[str, str]


def _iter_entry_points(group: str) -> Iterable[metadata.EntryPoint]:
    """Yield entry points for *group*, handling old/new metadata APIs."""
    try:
        eps = metadata.entry_points(group=group)
    except TypeError:  # pragma: no cover - legacy API fallback
        eps = metadata.entry_points().get(group, [])
    return list(eps)


def discover_entrypoint_adapters(group: str = ENTRYPOINT_GROUP) -> List[AdapterInfo]:
    """Return adapters registered via importlib entry points."""
    adapters: List[AdapterInfo] = []
    for ep in _iter_entry_points(group):
        identifier = f"entrypoint:{ep.name}"
        label = f"{ep.name} (pkg)"
        details: Dict[str, str] = {"value": ep.value}
        if getattr(ep, "module", None):
            details["module"] = ep.module or ""
        if getattr(ep, "dist", None):  # Python ≥3.11 adds dist metadata
            try:
                details["distribution"] = ep.dist.metadata["Name"]  # type: ignore[index]
            except Exception:  # pragma: no cover - metadata optional
                details["distribution"] = getattr(ep.dist, "name", "")
        adapters.append(
            AdapterInfo(
                identifier=identifier,
                display_name=label,
                spec=identifier,
                source="entrypoint",
                metadata=details,
            )
        )
    adapters.sort(key=lambda info: info.display_name.lower())
    return adapters


def discover_local_adapters(adapters_dir: Optional[Path] = None) -> List[AdapterInfo]:
    """Return adapters implemented as local .py files under *adapters_dir*."""
    base = (adapters_dir or DEFAULT_ADAPTERS_DIR).resolve()
    if not base.exists():
        return []

    results: List[AdapterInfo] = []
    for path in sorted(base.glob("*.py")):
        identifier = path.name
        results.append(
            AdapterInfo(
                identifier=identifier,
                display_name=f"{path.name} (local)",
                spec=str(path),
                source="file",
                metadata={"path": str(path)},
            )
        )
    return results


def discover_adapters(adapters_dir: Optional[Path] = None) -> List[AdapterInfo]:
    """Merge local and entry point adapters, de-duplicated by identifier."""
    items: Dict[str, AdapterInfo] = {}
    for info in discover_local_adapters(adapters_dir):
        items[info.identifier] = info
    for info in discover_entrypoint_adapters():
        items.setdefault(info.identifier, info)
    # Sort local adapters first, then entry points alphabetically
    return sorted(
        items.values(),
        key=lambda info: (0 if info.source == "file" else 1, info.display_name.lower()),
    )


def _normalize_path_candidate(path_str: str, adapters_dir: Optional[Path]) -> Optional[Path]:
    """Return a Path for *path_str* if it points to a real file, with fallbacks."""
    # file:// prefix support
    if path_str.startswith("file://"):
        path_str = path_str[7:]

    candidate = Path(path_str)
    if candidate.is_file():
        return candidate.resolve()

    # Treat bare filenames as residing in adapters_dir
    if adapters_dir is None:
        adapters_dir = DEFAULT_ADAPTERS_DIR
    candidate = adapters_dir / path_str
    if candidate.is_file():
        return candidate.resolve()

    return None


def _split_spec(spec: str, default_class: str) -> tuple[str, str]:
    """Split *spec* into module/path and class name."""
    path_part = spec
    class_name = default_class
    if ":" in spec:
        candidate_path, candidate_class = spec.rsplit(":", 1)
        if candidate_class and not any(sep in candidate_class for sep in (os.sep, os.altsep) if sep):
            path_part, class_name = candidate_path, candidate_class or default_class
    return path_part, class_name


def _load_class_from_entrypoint(name: str):
    for ep in _iter_entry_points(ENTRYPOINT_GROUP):
        if ep.name == name:
            obj = ep.load()
            if not inspect.isclass(obj):
                raise TypeError(
                    f"Entry point '{name}' resolved to {obj!r}, expected a class"
                )
            return obj
    raise ImportError(
        f"No adapter entry point named '{name}' found in group '{ENTRYPOINT_GROUP}'"
    )


def load_adapter_class(spec: str, *, default_class: str = "Adapter", adapters_dir: Optional[Path] = None):
    """Resolve *spec* into an adapter class.

    Supports:
      • filesystem specs: `/path/to/adapter.py:Class`
      • bare filenames resolved relative to the adapters directory
      • package entry points registered under the 'drybox.adapters' group via
        the `entrypoint:<name>` prefix (alias: `pkg:<name>`)
      • Python import paths (`package.module:Class`)
    """
    normalized = spec.strip()
    for prefix in ENTRYPOINT_PREFIXES:
        if normalized.startswith(prefix):
            name = normalized[len(prefix):]
            if not name:
                raise ImportError("Entry point spec is empty")
            return _load_class_from_entrypoint(name)

    path_part, class_name = _split_spec(normalized, default_class)

    # Attempt filesystem resolution first
    path_candidate = _normalize_path_candidate(path_part, adapters_dir)
    if path_candidate is not None:
        module_spec = importlib_util.spec_from_file_location(path_candidate.stem, path_candidate)
        if module_spec is None or module_spec.loader is None:
            raise ImportError(f"Cannot import adapter from {path_candidate}")
        module = importlib_util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)  # type: ignore[arg-type]
        try:
            return getattr(module, class_name)
        except AttributeError as exc:  # pragma: no cover - runtime error path
            raise ImportError(
                f"Module {path_candidate} has no class '{class_name}'"
            ) from exc

    # Otherwise treat as a Python import path
    try:
        module = import_module(path_part)
    except ModuleNotFoundError as exc:
        raise ImportError(f"Cannot resolve adapter module '{path_part}'") from exc
    try:
        return getattr(module, class_name)
    except AttributeError as exc:  # pragma: no cover - runtime error path
        raise ImportError(
            f"Module '{path_part}' has no attribute '{class_name}'"
        ) from exc


def resolve_identifier(identifier: str, adapters_dir: Optional[Path] = None) -> Optional[AdapterInfo]:
    """Return adapter metadata for *identifier*, if known."""
    all_infos = {info.identifier: info for info in discover_adapters(adapters_dir)}
    if identifier in all_infos:
        return all_infos[identifier]

    # Legacy bare filename fallback
    path = _normalize_path_candidate(identifier, adapters_dir)
    if path is not None:
        return AdapterInfo(
            identifier=identifier,
            display_name=f"{identifier} (local)",
            spec=str(path),
            source="file",
            metadata={"path": str(path)},
        )

    # Entry point fallback (scenario stored identifier but not currently installed)
    for prefix in ENTRYPOINT_PREFIXES:
        if identifier.startswith(prefix):
            name = identifier[len(prefix):]
            return AdapterInfo(
                identifier=identifier,
                display_name=f"{name} (pkg)",
                spec=identifier,
                source="entrypoint",
                metadata={},
            )

    return None

