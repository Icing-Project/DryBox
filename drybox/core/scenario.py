# MIT License
# drybox/core/scenario.py — validateur & résolveur centralisé des scénarios YAML
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml  # PyYAML
except ImportError as e:
    raise SystemExit("PyYAML is required. Install with `uv add pyyaml`") from e

try:
    import jsonschema
except ImportError as e:
    raise SystemExit("jsonschema is required. Install with `uv add jsonschema`") from e

# NEW: use package resources so scenarios/schema work after installation
try:
    from importlib import resources
except Exception as e:  # pragma: no cover
    raise SystemExit("Python 3.9+ importlib.resources is required") from e


class ScenarioValidationError(Exception):
    """Raised when the scenario YAML fails schema validation."""


@dataclass
class BearerConfig:
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResolved:
    mode: str
    duration_ms: int
    seed: int
    bearer: BearerConfig
    channel: Dict[str, Any]
    vocoder: Dict[str, Any]
    cfo_hz: int
    ppm: int
    frame_ms: int = 20  # cadence audio par défaut (v1)
    crypto: Dict[str, Any] = field(default_factory=dict)

    # ---------- Resource resolution helpers ----------

    @staticmethod
    def _read_text_from_pkg_path(pkg: str, *rel_parts: str) -> str | None:
        """
        Read a text resource from an installed package.
        Returns None if path doesn't exist.
        Works even when resources are inside wheels/zip.
        """
        try:
            base = resources.files(pkg)
        except ModuleNotFoundError:
            return None

        target = base
        for part in rel_parts:
            target = target.joinpath(part)

        # Convert to a real filesystem path if needed
        try:
            with resources.as_file(target) as real_path:
                if real_path.is_file():
                    return real_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        return None


    @staticmethod
    def _read_text_resource(pkg: str, name: str) -> Optional[str]:
        """
        Try to read a text resource from an installed package.
        Returns None if not found.
        """
        try:
            candidate = resources.files(pkg) / name
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        except ModuleNotFoundError:
            return None
        return None

    @staticmethod
    def _resolve_scenario_text(path_or_name: Union[str, pathlib.Path]) -> str:
        """
        Load scenario YAML from either:
        - a real filesystem path (relative to CWD or absolute)
        - a packaged resource under drybox.scenarios (by filename or with 'scenarios/' prefix)
        Returns the YAML text; raises FileNotFoundError if not found anywhere.
        """
        p = pathlib.Path(path_or_name)

        # 1) Direct filesystem path
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8")

        # 2) Packaged resource under drybox/scenarios
        # Accept "scenarios/foo.yaml" or just "foo.yaml"
        name = p.name
        text = ScenarioResolved._read_text_from_pkg_path("drybox", "scenarios", name)
        if text is not None:
            return text

        if p.parts and p.parts[0] == "scenarios" and len(p.parts) > 1:
            text = ScenarioResolved._read_text_from_pkg_path("drybox", *p.parts)
            if text is not None:
                return text

        raise FileNotFoundError(
            "Scenario file not found. Tried:\n"
            f"  - {p}\n"
            f"  - [pkg] drybox/scenarios/{name}"
        )

    @staticmethod
    def _load_schema() -> Dict[str, Any]:
        """
        Load JSON schema from packaged data (drybox/schema/scenario.schema.json).
        Falls back to repo-relative path only if running from a checkout without package data.
        """
        # Preferred: packaged resource drybox/schema/scenario.schema.json
        text = ScenarioResolved._read_text_from_pkg_path("drybox", "schema", "scenario.schema.json")
        if text is not None:
            return json.loads(text)

        # Fallback for editable checkouts
        fallback = pathlib.Path(__file__).resolve().parents[1] / "schema" / "scenario.schema.json"
        if fallback.exists():
            return json.loads(fallback.read_text(encoding="utf-8"))

        raise FileNotFoundError(
            "Could not locate schema 'scenario.schema.json' "
            "(looked in package 'drybox/schema' and repo 'schema/')."
        )

    @staticmethod
    def _apply_defaults(doc: Dict[str, Any]) -> Dict[str, Any]:
        # Top-level defaults
        out = dict(doc) if doc else {}
        out.setdefault("mode", "audio")
        out.setdefault("duration_ms", 60000)
        out.setdefault("seed", 0)
        out.setdefault("frame_ms", 20)
        out.setdefault("cfo_hz", 0)
        out.setdefault("ppm", 0)
        out.setdefault("bearer", {"type": "telco_volte_evs"})
        out.setdefault("channel", {})
        out.setdefault("vocoder", {})
        return out

    # ---------- Loading & validation ----------

    @classmethod
    def from_yaml(cls, path: Union[str, pathlib.Path]) -> "ScenarioResolved":
        # Load YAML text from FS or packaged resource (Step 3)
        yaml_text = cls._resolve_scenario_text(path)
        raw = yaml.safe_load(yaml_text) or {}
        if not isinstance(raw, dict):
            raise ScenarioValidationError("Scenario YAML must define a mapping at top level")

        # Defaults then validate
        doc = cls._apply_defaults(raw)
        schema = cls._load_schema()
        try:
            jsonschema.validate(instance=doc, schema=schema)
        except jsonschema.ValidationError as e:
            raise ScenarioValidationError(str(e)) from e

        # Normalize BearerConfig
        bearer_doc = doc["bearer"]
        btype = str(bearer_doc.get("type"))
        bparams = {k: v for k, v in bearer_doc.items() if k != "type"}

        crypto = dict(doc.get("crypto") or {})

        return cls(
            mode=str(doc["mode"]),
            duration_ms=int(doc["duration_ms"]),
            seed=int(doc["seed"]),
            bearer=BearerConfig(type=btype, params=bparams),
            channel=dict(doc.get("channel") or {}),
            vocoder=dict(doc.get("vocoder") or {}),
            cfo_hz=int(doc.get("cfo_hz", 0)),
            ppm=int(doc.get("ppm", 0)),
            frame_ms=int(doc.get("frame_ms", 20)),
            crypto=crypto,
        )

    # ---------- Sweep expansion ----------

    def expand_sweep(self) -> List[Tuple[str, "ScenarioResolved"]]:
        """
        If channel.snr_db is a list -> clone for each value.
        Returns list of (suffix, ScenarioResolved).
        """
        snr = self.channel.get("snr_db")
        if isinstance(snr, list) and snr:
            clones: List[Tuple[str, ScenarioResolved]] = []
            for v in snr:
                clone = ScenarioResolved(
                    mode=self.mode,
                    duration_ms=self.duration_ms,
                    seed=self.seed,
                    bearer=BearerConfig(type=self.bearer.type, params=dict(self.bearer.params)),
                    channel={**self.channel, "snr_db": v},
                    vocoder=dict(self.vocoder),
                    cfo_hz=self.cfo_hz,
                    ppm=self.ppm,
                    frame_ms=self.frame_ms,
                )
                suffix = f"snr_{int(v) if isinstance(v, (int, float)) and v == int(v) else v}"
                clones.append((suffix, clone))
            return clones
        return [("", self)]

    # ---------- Serialization ----------

    def to_resolved_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "duration_ms": self.duration_ms,
            "seed": self.seed,
            "bearer": {"type": self.bearer.type, **self.bearer.params},
            "channel": dict(self.channel),
            "vocoder": dict(self.vocoder),
            "cfo_hz": self.cfo_hz,
            "ppm": self.ppm,
            "frame_ms": self.frame_ms,
            # "crypto": self.crypto # you might want to display them
        }

    def write_resolved_yaml(self, out_path: Union[str, pathlib.Path]) -> None:
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fp:
            yaml.safe_dump(self.to_resolved_dict(), fp, sort_keys=False)
