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

    # ---------- Loading & validation ----------

    @staticmethod
    def _schema_path() -> pathlib.Path:
        # repo_root/schema/scenario.schema.json
        return pathlib.Path(__file__).resolve().parents[2] / "schema" / "scenario.schema.json"

    @staticmethod
    def _load_schema() -> Dict[str, Any]:
        with open(ScenarioResolved._schema_path(), "r", encoding="utf-8") as fp:
            return json.load(fp)

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

    @classmethod
    def from_yaml(cls, path: Union[str, pathlib.Path]) -> "ScenarioResolved":
        p = pathlib.Path(path)
        with open(p, "r", encoding="utf-8") as fp:
            raw = yaml.safe_load(fp) or {}
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
