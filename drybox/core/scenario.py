# drybox/core/scenario.py
# MIT License
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Tuple, Optional, Union
import pathlib

try:
    import yaml  # PyYAML
except ImportError as e:
    raise SystemExit("PyYAML is required. Install with `uv add pyyaml`.") from e


# ---- Defaults (utilisés par runner/tests) ------------------------------------
DEFAULT_TICK_MS = 10
DEFAULT_SEED = 0
DEFAULT_MODE = "audio"
DEFAULT_FRAME_MS = 20


# ---- Exceptions --------------------------------------------------------------
class ScenarioValidationError(Exception):
    """Erreur de validation du scénario (YAML invalide, type hors domaine, etc.)."""
    pass


# ---- Modèles -----------------------------------------------------------------
@dataclass
class BearerConfig:
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResolved:
    # Champs communs
    mode: str = DEFAULT_MODE                 # "audio" | "byte"
    duration_ms: int = 60_000
    seed: int = DEFAULT_SEED
    frame_ms: int = DEFAULT_FRAME_MS

    # Réseau / Radio
    bearer: BearerConfig = field(default_factory=lambda: BearerConfig(type="telco_volte_evs"))
    channel: Dict[str, Any] = field(default_factory=dict)   # Mode B (mais utilisé pour sweep snr_db)
    vocoder: Dict[str, Any] = field(default_factory=dict)   # Mode B

    # Divers
    cfo_hz: int = 0
    ppm: int = 0

    # Crypto (ne jamais écrire dans le YAML résolu)
    crypto: Dict[str, Any] = field(default_factory=dict)

    # ---- Builders ------------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: Union[str, pathlib.Path]) -> "ScenarioResolved":
        """Charge et valide depuis un fichier YAML."""
        p = pathlib.Path(path)
        try:
            with open(p, "r", encoding="utf-8") as fp:
                raw = yaml.safe_load(fp) or {}
        except Exception as e:
            raise ScenarioValidationError(f"Cannot read scenario YAML: {e}") from e
        return cls.from_yaml_dict(raw, source_path=str(p))

    @classmethod
    def from_yaml_dict(cls, doc: Dict[str, Any], *, source_path: Optional[str] = None) -> "ScenarioResolved":
        """Construit et valide depuis un dict Python (utilisé par les tests)."""
        try:
            mode = str(doc.get("mode", DEFAULT_MODE))
            if mode not in ("audio", "byte"):
                raise ScenarioValidationError("mode must be 'audio' or 'byte'")

            duration_ms = cls._as_int(doc.get("duration_ms", 60_000), "duration_ms")
            seed = cls._as_int(doc.get("seed", DEFAULT_SEED), "seed")
            frame_ms = cls._as_int(doc.get("frame_ms", DEFAULT_FRAME_MS), "frame_ms")

            # bearer
            bearer_doc = doc.get("bearer") or {"type": "telco_volte_evs"}
            if not isinstance(bearer_doc, dict) or "type" not in bearer_doc:
                raise ScenarioValidationError("bearer.type is required")
            btype = str(bearer_doc["type"])
            bparams = {k: v for k, v in bearer_doc.items() if k != "type"}
            if "latency_ms" in bparams:
                cls._as_int(bparams["latency_ms"], "latency_ms")
            if "mtu_bytes" in bparams:
                cls._as_int(bparams["mtu_bytes"], "mtu_bytes")

            # channel
            channel = dict(doc.get("channel") or {})
            if "snr_db" in channel:
                channel["snr_db"] = cls._as_number_or_number_list(channel["snr_db"], "snr_db")

            # vocoder
            vocoder = dict(doc.get("vocoder") or {})

            cfo_hz = int(doc.get("cfo_hz", 0))
            ppm = int(doc.get("ppm", 0))

            # crypto (clé privée fournie optionnellement) — on ne valide pas ici le format exact,
            # la résolution des clés se fait dans core/crypto_keys.py
            crypto = dict(doc.get("crypto") or {})

            return cls(
                mode=mode,
                duration_ms=duration_ms,
                seed=seed,
                frame_ms=frame_ms,
                bearer=BearerConfig(type=btype, params=bparams),
                channel=channel,
                vocoder=vocoder,
                cfo_hz=cfo_hz,
                ppm=ppm,
                crypto=crypto,
            )
        except ScenarioValidationError:
            raise
        except Exception as e:
            # On encapsule toute autre erreur en validation error
            raise ScenarioValidationError(str(e)) from e

    # ---- Instance API attendue par les tests ---------------------------------
    def expand_sweep(self) -> List[Tuple[str, "ScenarioResolved"]]:
        """
        Duplique le scénario pour chaque valeur listée des champs acceptant des sweeps.
        v1: `channel.snr_db` peut être un nombre ou une liste de nombres.
        """
        clones: List[Tuple[str, ScenarioResolved]] = []
        snr = self.channel.get("snr_db")
        if isinstance(snr, list) and snr:
            for v in snr:
                clone = replace(self)
                clone.channel = {**self.channel, "snr_db": v}
                suffix = f"snr_{int(v) if isinstance(v, (int, float)) and v == int(v) else v}"
                clones.append((suffix, clone))
            return clones
        # Pas de sweep → un seul clone vide
        return [("", self)]

    def write_resolved_yaml(self, path: Union[str, pathlib.Path]) -> None:
        """
        Écrit un fichier YAML "résolu" **sans** secrets (crypto absent).
        Utilisé par les tests pour vérifier l’écriture.
        """
        out = pathlib.Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fp:
            yaml.safe_dump(self.to_public_dict(), fp, sort_keys=False)

    # ---- Utilitaires ---------------------------------------------------------
    def to_public_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable sans secrets (crypto exclu)."""
        return {
            "mode": self.mode,
            "duration_ms": self.duration_ms,
            "seed": self.seed,
            "frame_ms": self.frame_ms,
            "bearer": {"type": self.bearer.type, **self.bearer.params},
            "channel": self.channel,
            "vocoder": self.vocoder,
            "cfo_hz": self.cfo_hz,
            "ppm": self.ppm,
            # crypto volontairement omis
        }

    @staticmethod
    def _as_int(v: Any, name: str) -> int:
        if isinstance(v, bool) or not isinstance(v, (int,)):
            raise ScenarioValidationError(f"{name} must be integer")
        return int(v)

    @staticmethod
    def _as_number_or_number_list(v: Any, name: str) -> Any:
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, list) and all(isinstance(x, (int, float)) for x in v):
            return v
        raise ScenarioValidationError(f"{name} must be a number or a list[number]")


# ---- Compat (runner pouvait importer une fonction) ---------------------------
def expand_sweep(scen: ScenarioResolved) -> List[Tuple[str, ScenarioResolved]]:
    """Reste compatible avec le runner existant qui importait expand_sweep() en fonction."""
    return scen.expand_sweep()
