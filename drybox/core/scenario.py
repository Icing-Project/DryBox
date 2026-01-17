# MIT License
# drybox/core/scenario.py — schema-based scenario validator
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Union

try:
    import yaml  # PyYAML
except ImportError as e:
    raise SystemExit("PyYAML is required. Install with `uv add pyyaml`") from e

try:
    import jsonschema
except ImportError as e:
    raise SystemExit("jsonschema is required. Install with `uv add jsonschema`") from e

from drybox.core.paths import resolve_resource_path, SCENARIOS_DIR


class ScenarioValidationError(Exception):
    """Raised when the scenario YAML fails schema validation."""


@dataclass
class ScenarioResolved:
    mode: str
    duration_ms: int
    seed: int
    network: Dict[str, Any]
    left: Dict[str, Any]
    right: Dict[str, Any]
    cfo_hz: int
    ppm: int
    crypto: Dict[str, Any] = field(default_factory=dict)

    # ---------- Resource resolution helpers ----------

    @staticmethod
    def _resolve_scenario_text(path_or_name: Union[str, pathlib.Path]) -> str:
        p = pathlib.Path(path_or_name)

        # 1. Direct file path
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8")

        # 2. Try as scenario name in scenarios directory
        name = p.name
        scenario_path = resolve_resource_path("scenarios", name)
        if scenario_path and scenario_path.is_file():
            return scenario_path.read_text(encoding="utf-8")

        # 3. Structured path fallback (scenarios/subdir/file.yaml)
        if p.parts and p.parts[0] == "scenarios" and len(p.parts) > 1:
            scenario_path = resolve_resource_path(*p.parts)
            if scenario_path and scenario_path.is_file():
                return scenario_path.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"Scenario not found. Tried:\n"
            f"  - {p}\n"
            f"  - {SCENARIOS_DIR / name}"
        )

    @staticmethod
    def _load_schema() -> Dict[str, Any]:
        schema_path = resolve_resource_path("schema", "scenario.schema.json")
        if schema_path:
            return json.loads(schema_path.read_text(encoding="utf-8"))
        raise FileNotFoundError("Could not locate schema 'scenario.schema.json'")

    @staticmethod
    def _apply_defaults(doc: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(doc) if doc else {}
        out.setdefault("mode", "audio")
        out.setdefault("duration_ms", 2000)
        out.setdefault("seed", 123456)
        out.setdefault("cfo_hz", 0)
        out.setdefault("ppm", 0)
        out.setdefault("network", {"bearer": "volte_evs"})
        out.setdefault("left", {"adapter": "nade-python", "gain": 1.0})
        out.setdefault("right", {"adapter": "nade-python", "gain": 1.0})
        return out

    # ---------- Loading & validation ----------

    @classmethod
    def from_yaml(cls, path: Union[str, pathlib.Path]) -> "ScenarioResolved":
        yaml_text = cls._resolve_scenario_text(path)
        raw = yaml.safe_load(yaml_text) or {}
        if not isinstance(raw, dict):
            raise ScenarioValidationError("Scenario YAML must define a mapping at top level")

        doc = cls._apply_defaults(raw)
        schema = cls._load_schema()
        try:
            jsonschema.validate(instance=doc, schema=schema)
        except jsonschema.ValidationError as e:
            raise ScenarioValidationError(str(e)) from e

        return cls(
            mode=str(doc["mode"]),
            duration_ms=int(doc["duration_ms"]),
            seed=int(doc["seed"]),
            network=dict(doc.get("network") or {}),
            left=dict(doc.get("left") or {}),
            right=dict(doc.get("right") or {}),
            cfo_hz=int(doc.get("cfo_hz", 0)),
            ppm=int(doc.get("ppm", 0)),
            crypto=dict(doc.get("crypto") or {}),
        )

    # ---------- Sweep expansion ----------

    def expand_sweep(self) -> List[Tuple[str, "ScenarioResolved"]]:
        snr = self.left.get("modem", {}).get("snr_db")
        if isinstance(snr, list) and snr:
            clones: List[Tuple[str, ScenarioResolved]] = []
            for v in snr:
                clone_left = dict(self.left)
                clone_left["modem"] = dict(clone_left.get("modem", {}), snr_db=v)
                clone = ScenarioResolved(
                    mode=self.mode,
                    duration_ms=self.duration_ms,
                    seed=self.seed,
                    network=dict(self.network),
                    left=clone_left,
                    right=dict(self.right),
                    cfo_hz=self.cfo_hz,
                    ppm=self.ppm,
                    crypto=dict(self.crypto),
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
            "network": dict(self.network),
            "left": dict(self.left),
            "right": dict(self.right),
            "cfo_hz": self.cfo_hz,
            "ppm": self.ppm,
            "crypto": dict(self.crypto),
        }

    def write_resolved_yaml(self, out_path: Union[str, pathlib.Path]) -> None:
        p = pathlib.Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fp:
            yaml.safe_dump(self.to_resolved_dict(), fp, sort_keys=False)
