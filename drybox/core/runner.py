# drybox/core/runner.py
# MIT License
# DryBox Runner v1 — boucle de simulation déterministe + I/O adaptateurs Nade
# - Tick logique (10 ms par défaut), on_timer() avant I/O
# - Mode A (ByteLink) opérationnel (Mode B: hooks prêts, à implémenter)
# - Scénarios YAML (défauts + sweep)
# - SAR-lite intégré si MTU < SDU
# - Métriques CSV, events.jsonl, capture .dbxcap (TLV simple, rejouable)
from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import os
import pathlib
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml  # PyYAML
except ImportError as e:
    raise SystemExit(
        "PyYAML is required. Install with `uv add pyyaml` or `pip install pyyaml`."
    ) from e

# Local deps
from drybox.net.bearers import (
    DatagramBearer,
    make_bearer,
    BearerStatsSnapshot,
)
from drybox.net.sar_lite import SARFragmenter, SARReassembler

# --------- Constantes / Defaults ----------
DEFAULT_TICK_MS = 10
DEFAULT_MODE = "audio"  # per brief; ByteLink reste pleinement supporté via bearer datagramme
DEFAULT_FRAME_MS = 20
DEFAULT_SEED = 0
DEFAULT_SDU_MAX = 1024  # avant fragmentation SAR (négociable via capabilities)
CSV_HEADER = [
    "t_ms",
    "side",
    "layer",
    "event",
    "rtt_ms_est",
    "latency_ms",
    "jitter_ms",
    "loss_rate",
    "reorder_rate",
    "goodput_bps",
    "snr_db_est",
    "ber",
    "per",
    "cfo_hz_est",
    "lock_ratio",
    "hs_time_ms",
    "rekey_ms",
    "aead_fail_cnt",
]

# Layers/events (sémantique volontairement simple)
LAYER_BYTELINK = "bytelink"
LAYER_BEARER = "bearer"
EVENT_TX = "tx"
EVENT_RX = "rx"
EVENT_DROP = "drop"
EVENT_TICK = "tick"


# --------- Utils chemin/chargement ----------
def _load_class_from_path(spec: str):
    """
    Charge une classe à partir d'une spécification 'path/to/module.py:ClassName'.
    Compatible chemins relatifs. Pas de cache module global (isolation simple).
    """
    if ":" not in spec:
        raise ValueError(f"Adapter spec must be 'path.py:Class', got: {spec}")
    path_str, class_name = spec.split(":", 1)
    mod_path = pathlib.Path(path_str).resolve()
    if not mod_path.exists():
        raise FileNotFoundError(f"Adapter module not found: {mod_path}")
    module_name = f"dbx_adapter_{mod_path.stem}_{abs(hash(mod_path))}"
    spec_obj = importlib.util.spec_from_file_location(module_name, str(mod_path))
    if spec_obj is None or spec_obj.loader is None:
        raise ImportError(f"Cannot load module from: {mod_path}")
    module = importlib.util.module_from_spec(spec_obj)
    spec_obj.loader.exec_module(module)
    cls = getattr(module, class_name, None)
    if cls is None:
        raise AttributeError(f"Class '{class_name}' not found in {mod_path}")
    return cls


# --------- Scénarios ----------
@dataclass
class BearerConfig:
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    mode: str = DEFAULT_MODE  # "audio" | "byte"
    duration_ms: int = 60_000
    seed: int = DEFAULT_SEED
    bearer: BearerConfig = field(default_factory=lambda: BearerConfig(type="telco_volte_evs"))
    channel: Dict[str, Any] = field(default_factory=dict)  # Mode B (stub pour v1)
    vocoder: Dict[str, Any] = field(default_factory=dict)  # Mode B (stub pour v1)
    cfo_hz: int = 0
    ppm: int = 0

    @staticmethod
    def from_yaml(doc: Dict[str, Any]) -> "Scenario":
        # Defaults
        mode = doc.get("mode", DEFAULT_MODE)
        duration_ms = int(doc.get("duration_ms", 60_000))
        seed = int(doc.get("seed", DEFAULT_SEED))
        bearer = doc.get("bearer") or {"type": "telco_volte_evs"}
        channel = doc.get("channel") or {}
        vocoder = doc.get("vocoder") or {}
        cfo_hz = int(doc.get("cfo_hz", 0))
        ppm = int(doc.get("ppm", 0))
        return Scenario(
            mode=mode,
            duration_ms=duration_ms,
            seed=seed,
            bearer=BearerConfig(type=bearer["type"], params={k: v for k, v in bearer.items() if k != "type"}),
            channel=channel,
            vocoder=vocoder,
            cfo_hz=cfo_hz,
            ppm=ppm,
        )


def _expand_sweep(scen: Scenario) -> List[Tuple[str, Scenario]]:
    """
    Si un champ accepte une liste (ex: channel.snr_db), duplique le scénario par valeur.
    Produit des paires (suffix_path, scenario_clone).
    """
    clones: List[Tuple[str, Scenario]] = []

    # Actuellement: sweep sur channel.snr_db (Mode B)
    snr = scen.channel.get("snr_db")
    if isinstance(snr, list) and snr:
        for v in snr:
            clone = Scenario.from_yaml(
                {
                    "mode": scen.mode,
                    "duration_ms": scen.duration_ms,
                    "seed": scen.seed,
                    "bearer": {"type": scen.bearer.type, **scen.bearer.params},
                    "channel": {**scen.channel, "snr_db": v},
                    "vocoder": scen.vocoder,
                    "cfo_hz": scen.cfo_hz,
                    "ppm": scen.ppm,
                }
            )
            suffix = f"snr_{v}"
            clones.append((suffix, clone))
        return clones

    # Aucun sweep détecté -> scénario unique
    clones.append(("", scen))
    return clones


# --------- Métriques & captures ----------
class MetricsWriter:
    def __init__(self, csv_path: pathlib.Path, events_path: pathlib.Path):
        self._csv_fp = open(csv_path, "w", newline="")
        self._csv = csv.DictWriter(self._csv_fp, fieldnames=CSV_HEADER)
        self._csv.writeheader()
        self._events_fp = open(events_path, "w", encoding="utf-8")

    def write_metric(
        self,
        *,
        t_ms: int,
        side: str,
        layer: str,
        event: str,
        rtt_ms_est: Optional[float] = None,
        latency_ms: Optional[float] = None,
        jitter_ms: Optional[float] = None,
        loss_rate: Optional[float] = None,
        reorder_rate: Optional[float] = None,
        goodput_bps: Optional[float] = None,
        snr_db_est: Optional[float] = None,
        ber: Optional[float] = None,
        per: Optional[float] = None,
        cfo_hz_est: Optional[float] = None,
        lock_ratio: Optional[float] = None,
        hs_time_ms: Optional[float] = None,
        rekey_ms: Optional[float] = None,
        aead_fail_cnt: Optional[int] = None,
    ) -> None:
        row = {
            "t_ms": t_ms,
            "side": side,
            "layer": layer,
            "event": event,
            "rtt_ms_est": _fmt(rtt_ms_est),
            "latency_ms": _fmt(latency_ms),
            "jitter_ms": _fmt(jitter_ms),
            "loss_rate": _fmt(loss_rate),
            "reorder_rate": _fmt(reorder_rate),
            "goodput_bps": _fmt(goodput_bps),
            "snr_db_est": _fmt(snr_db_est),
            "ber": _fmt(ber),
            "per": _fmt(per),
            "cfo_hz_est": _fmt(cfo_hz_est),
            "lock_ratio": _fmt(lock_ratio),
            "hs_time_ms": _fmt(hs_time_ms),
            "rekey_ms": _fmt(rekey_ms),
            "aead_fail_cnt": aead_fail_cnt if aead_fail_cnt is not None else "",
        }
        self._csv.writerow(row)

    def write_event(self, t_ms: int, side: str, typ: str, payload: Dict[str, Any]) -> None:
        rec = {"t_ms": t_ms, "side": side, "type": typ, "payload": payload}
        self._events_fp.write(json.dumps(rec) + "\n")

    def close(self) -> None:
        try:
            self._csv_fp.flush()
            self._csv_fp.close()
        finally:
            self._events_fp.flush()
            self._events_fp.close()


def _fmt(x: Optional[float]) -> str:
    if x is None:
        return ""
    return f"{x:.6f}"


class DbxCapWriter:
    """
    Fichier binaire TLV rejouable.
    Format:
      magic: b'DBXC' (4)
      version: u8 (=1)
      puis records:
        t_ms: u64le
        side: u8  (0=L->R, 1=R->L)
        layer: u8 (0=bytelink, 1=bearer)
        event: u8 (0=tx,1=rx,2=drop)
        len: u32le
        data: bytes
    """
    MAGIC = b"DBXC"
    VERSION = 1

    EV_MAP = {EVENT_TX: 0, EVENT_RX: 1, EVENT_DROP: 2}
    LAYER_MAP = {LAYER_BYTELINK: 0, LAYER_BEARER: 1}
    SIDE_MAP = {"L": 0, "R": 1}

    def __init__(self, path: pathlib.Path):
        self._fp = open(path, "wb")
        self._fp.write(self.MAGIC)
        self._fp.write(bytes([self.VERSION]))

    def write(self, *, t_ms: int, side: str, layer: str, event: str, data: bytes) -> None:
        import struct

        side_b = self.SIDE_MAP.get(side, 0)
        layer_b = self.LAYER_MAP.get(layer, 0)
        ev_b = self.EV_MAP.get(event, 0)
        rec = struct.pack("<QBBB", int(t_ms), side_b, layer_b, ev_b)
        self._fp.write(rec)
        self._fp.write(struct.pack("<I", len(data)))
        self._fp.write(data)

    def close(self) -> None:
        self._fp.flush()
        self._fp.close()


# --------- Contexte adaptateur ----------
class AdapterCtx:
    def __init__(self, *, side: str, rng: random.Random, get_time_ms, emit_event, config: Dict[str, Any]):
        self.side = side
        self.rng = rng
        self._get_time_ms = get_time_ms
        self._emit_event = emit_event
        self.config = config  # e.g., {"tick_ms":10, "mode":"byte|audio", "sdu_max_bytes":1024}

    def now_ms(self) -> int:
        return self._get_time_ms()

    def emit_event(self, typ: str, payload: Dict[str, Any]) -> None:
        self._emit_event(self.side, typ, payload)


# --------- Runner ----------
class Runner:
    def __init__(
        self,
        *,
        scenario: Scenario,
        left_adapter_spec: str,
        right_adapter_spec: str,
        out_dir: pathlib.Path,
        tick_ms: int = DEFAULT_TICK_MS,
        seed: int = DEFAULT_SEED,
        ui_enabled: bool = True,
    ):
        self.scenario = scenario
        self.left_adapter_spec = left_adapter_spec
        self.right_adapter_spec = right_adapter_spec
        self.out_dir = out_dir
        self.tick_ms = tick_ms
        self.seed = seed
        self.ui_enabled = ui_enabled

        # RNG global seedé
        self.rng = random.Random(seed)

        # Out dirs
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = MetricsWriter(self.out_dir / "metrics.csv", self.out_dir / "events.jsonl")
        self.cap = DbxCapWriter(self.out_dir / "capture.dbxcap")

        # Placeholders
        self.t_ms: int = 0

    def _load_adapter(self, spec: str, side: str):
        cls = _load_class_from_path(spec)
        inst = cls()
        # Découverte / capabilities (facultatif mais recommandé)
        caps = {}
        if hasattr(inst, "nade_capabilities"):
            try:
                caps = inst.nade_capabilities()  # type: ignore[attr-defined]
            except Exception:
                caps = {}
        # Initialisation
        cfg = {
            "tick_ms": self.tick_ms,
            "side": side,
            "seed": self.seed,
            "mode": self.scenario.mode,
            "sdu_max_bytes": DEFAULT_SDU_MAX,  # hint; adapter peut renvoyer sdu_max + prefs par capabilities
        }
        if hasattr(inst, "init"):
            inst.init(cfg)  # type: ignore[attr-defined]
        # Contexte
        ctx = AdapterCtx(
            side=side,
            rng=self.rng,
            get_time_ms=lambda: self.t_ms,
            emit_event=lambda side, typ, payload: self.metrics.write_event(self.t_ms, side, typ, payload),
            config=cfg,
        )
        if hasattr(inst, "start"):
            inst.start(ctx)  # type: ignore[attr-defined]
        return inst, caps

    def _require_mode_supported(self, caps_left: Dict[str, Any], caps_right: Dict[str, Any]) -> None:
        mode = self.scenario.mode
        if mode == "audio":
            ok = caps_left.get("audioblock", True) and caps_right.get("audioblock", True)
        else:
            ok = caps_left.get("bytelink", True) and caps_right.get("bytelink", True)
        if not ok:
            raise SystemExit(4)  # scénario invalide

    def run(self) -> int:
        # Charge adaptateurs
        left, left_caps = self._load_adapter(self.left_adapter_spec, "L")
        right, right_caps = self._load_adapter(self.right_adapter_spec, "R")
        self._require_mode_supported(left_caps, right_caps)

        # Configure bearer (datagram mode) — même en "audio", on garde la couche transport pour MTU/tempo
        bearer_l2r: DatagramBearer = make_bearer(self.scenario.bearer.type, self.scenario.bearer.params, self.rng)
        bearer_r2l: DatagramBearer = make_bearer(self.scenario.bearer.type, self.scenario.bearer.params, self.rng)

        # SAR-lite: activé si MTU < SDU_MAX (spec v1: SDU max 1024 — négociable via capabilities)
        sdu_max = DEFAULT_SDU_MAX
        mtu = int(self.scenario.bearer.params.get("mtu_bytes", sdu_max))
        sar_active = mtu < sdu_max
        frag_l2r = SARFragmenter(mtu_bytes=mtu) if sar_active else None
        frag_r2l = SARFragmenter(mtu_bytes=mtu) if sar_active else None

        # Réassemblage (timeout = 2 × RTT_est). RTT_est ~ 2 × latency_ms si connu
        lat_ms = int(self.scenario.bearer.params.get("latency_ms", 60))
        rtt_est = max(1, 2 * lat_ms)
        reas_l = SARReassembler(rtt_estimate_ms=2 * rtt_est, expect_header=sar_active)
        reas_r = SARReassembler(rtt_estimate_ms=2 * rtt_est, expect_header=sar_active)

        # Boucle logique
        duration = int(self.scenario.duration_ms)
        budget_per_tick = 64  # SDUs max par tick
        last_ui_print = -10_000

        # Stats pour goodput (fenêtre 1 s)
        bytes_rx_l = 0
        bytes_rx_r = 0
        window_start_ms = 0

        try:
            while self.t_ms <= duration:
                # 1) tick côté adaptateurs (avant toute I/O)
                for a in (left, right):
                    if hasattr(a, "on_timer"):
                        a.on_timer(self.t_ms)  # type: ignore[attr-defined]

                # 2) TX ByteLink (L->R)
                if self.scenario.mode in ("byte", "audio"):  # ByteLink existe toujours (Mode B à étoffer plus tard)
                    # LEFT -> BEARER
                    if hasattr(left, "poll_link_tx"):
                        try:
                            sdus: List[bytes]
                            res = left.poll_link_tx(budget_per_tick)  # type: ignore[attr-defined]
                            # Adapter peut retourner liste de bytes ou liste de (bytes, t_ms_logique)
                            sdus = [b if isinstance(b, (bytes, bytearray)) else b[0] for b in res]  # type: ignore[index]
                        except Exception:
                            sdus = []
                        for sdu in sdus:
                            payloads = [sdu]
                            if sar_active and frag_l2r is not None:
                                payloads = frag_l2r.fragment(sdu)
                            for p in payloads:
                                bearer_l2r.send(p, now_ms=self.t_ms)
                                self.cap.write(t_ms=self.t_ms, side="L", layer=LAYER_BEARER, event=EVENT_TX, data=bytes(p))
                                self.metrics.write_metric(
                                    t_ms=self.t_ms, side="L", layer=LAYER_BEARER, event=EVENT_TX, rtt_ms_est=rtt_est
                                )

                    # RIGHT -> BEARER
                    if hasattr(right, "poll_link_tx"):
                        try:
                            sdus_r: List[bytes]
                            res_r = right.poll_link_tx(budget_per_tick)  # type: ignore[attr-defined]
                            sdus_r = [b if isinstance(b, (bytes, bytearray)) else b[0] for b in res_r]  # type: ignore[index]
                        except Exception:
                            sdus_r = []
                        for sdu in sdus_r:
                            payloads = [sdu]
                            if sar_active and frag_r2l is not None:
                                payloads = frag_r2l.fragment(sdu)
                            for p in payloads:
                                bearer_r2l.send(p, now_ms=self.t_ms)
                                self.cap.write(t_ms=self.t_ms, side="R", layer=LAYER_BEARER, event=EVENT_TX, data=bytes(p))
                                self.metrics.write_metric(
                                    t_ms=self.t_ms, side="R", layer=LAYER_BEARER, event=EVENT_TX, rtt_ms_est=rtt_est
                                )

                # 3) Delivery via bearer (L->R)
                for dat in bearer_l2r.poll_deliver(self.t_ms):
                    self.cap.write(t_ms=self.t_ms, side="L", layer=LAYER_BEARER, event=EVENT_RX, data=bytes(dat.payload))
                    lat = self.t_ms - dat.sent_ms
                    # Réassemblage -> SDU complet
                    sdu: Optional[bytes] = dat.payload
                    if sar_active:
                        sdu = reas_r.push_fragment(dat.payload, now_ms=self.t_ms)
                    if sdu is not None and hasattr(right, "on_link_rx"):
                        right.on_link_rx(sdu, )  # type: ignore[attr-defined]
                        self.metrics.write_metric(
                            t_ms=self.t_ms,
                            side="R",
                            layer=LAYER_BYTELINK,
                            event=EVENT_RX,
                            latency_ms=float(lat),
                            jitter_ms=bearer_l2r.stats().jitter_ms,
                            loss_rate=bearer_l2r.stats().loss_rate,
                            reorder_rate=bearer_l2r.stats().reorder_rate,
                        )
                        bytes_rx_r += len(sdu)

                # 4) Delivery via bearer (R->L)
                for dat in bearer_r2l.poll_deliver(self.t_ms):
                    self.cap.write(t_ms=self.t_ms, side="R", layer=LAYER_BEARER, event=EVENT_RX, data=bytes(dat.payload))
                    lat = self.t_ms - dat.sent_ms
                    sdu: Optional[bytes] = dat.payload
                    if sar_active:
                        sdu = reas_l.push_fragment(dat.payload, now_ms=self.t_ms)
                    if sdu is not None and hasattr(left, "on_link_rx"):
                        left.on_link_rx(sdu, )  # type: ignore[attr-defined]
                        self.metrics.write_metric(
                            t_ms=self.t_ms,
                            side="L",
                            layer=LAYER_BYTELINK,
                            event=EVENT_RX,
                            latency_ms=float(lat),
                            jitter_ms=bearer_r2l.stats().jitter_ms,
                            loss_rate=bearer_r2l.stats().loss_rate,
                            reorder_rate=bearer_r2l.stats().reorder_rate,
                        )
                        bytes_rx_l += len(sdu)

                # 5) Goodput (fenêtre glissante 1 s)
                if self.t_ms - window_start_ms >= 1000:
                    g_l = (bytes_rx_l * 8) / max(1, self.t_ms - window_start_ms) * 1000.0
                    g_r = (bytes_rx_r * 8) / max(1, self.t_ms - window_start_ms) * 1000.0
                    self.metrics.write_metric(
                        t_ms=self.t_ms, side="L", layer=LAYER_BYTELINK, event=EVENT_TICK, goodput_bps=g_l
                    )
                    self.metrics.write_metric(
                        t_ms=self.t_ms, side="R", layer=LAYER_BYTELINK, event=EVENT_TICK, goodput_bps=g_r
                    )
                    bytes_rx_l = 0
                    bytes_rx_r = 0
                    window_start_ms = self.t_ms

                # 6) UI minimale
                if self.ui_enabled and (self.t_ms - last_ui_print) >= 1000:
                    # Log simple de progression
                    stats_l: BearerStatsSnapshot = bearer_l2r.stats()
                    stats_r: BearerStatsSnapshot = bearer_r2l.stats()
                    print(
                        f"[{self.t_ms:6d} ms] "
                        f"L->R loss={stats_l.loss_rate:.3f} reord={stats_l.reorder_rate:.3f} jitter={stats_l.jitter_ms:.1f}ms | "
                        f"R->L loss={stats_r.loss_rate:.3f} reord={stats_r.reorder_rate:.3f} jitter={stats_r.jitter_ms:.1f}ms",
                        file=sys.stderr,
                    )
                    last_ui_print = self.t_ms

                # 7) Avance horloge
                self.t_ms += self.tick_ms

            return 0  # OK (v1: pas d'évaluation de seuil intégrée ici)
        finally:
            # Teardown
            for a in (left, right):
                if hasattr(a, "stop"):
                    try:
                        a.stop()  # type: ignore[attr-defined]
                    except Exception:
                        pass
            self.metrics.close()
            self.cap.close()


# --------- CLI ----------
def parse_args(argv: Optional[List[str]] = None):
    p = argparse.ArgumentParser(description="DryBox v1 Runner")
    p.add_argument("--scenario", required=True, help="YAML scenario path")
    p.add_argument("--left", required=True, help="Adapter spec: path/to/adapter.py:Class")
    p.add_argument("--right", required=True, help="Adapter spec: path/to/adapter.py:Class")
    p.add_argument("--out", required=True, help="Output directory for this run (or sweep root)")
    p.add_argument("--tick-ms", type=int, default=DEFAULT_TICK_MS)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--ui", action="store_true", default=True)
    p.add_argument("--no-ui", action="store_false", dest="ui")
    p.add_argument("--plot", action="store_true", help="(reserved)")
    p.add_argument("--sweep-parallel", type=int, default=1, help="(reserved) parallelism per sweep value")
    return p.parse_args(argv)


def load_yaml(path: pathlib.Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    scen_path = pathlib.Path(args.scenario).resolve()
    doc = load_yaml(scen_path)
    base = Scenario.from_yaml(doc)
    clones = _expand_sweep(base)

    root_out = pathlib.Path(args.out).resolve()
    rc = 0
    for suffix, scen in clones:
        out_dir = root_out if not suffix else root_out / suffix
        out_dir.mkdir(parents=True, exist_ok=True)
        # Sauvegarde le scénario résolu pour le run
        with open(out_dir / "scenario.resolved.yaml", "w", encoding="utf-8") as fp:
            yaml.safe_dump(
                {
                    "mode": scen.mode,
                    "duration_ms": scen.duration_ms,
                    "seed": scen.seed,
                    "bearer": {"type": scen.bearer.type, **scen.bearer.params},
                    "channel": scen.channel,
                    "vocoder": scen.vocoder,
                    "cfo_hz": scen.cfo_hz,
                    "ppm": scen.ppm,
                },
                fp,
                sort_keys=False,
            )
        runner = Runner(
            scenario=scen,
            left_adapter_spec=args.left,
            right_adapter_spec=args.right,
            out_dir=out_dir,
            tick_ms=args.tick_ms,
            seed=args.seed,
            ui_enabled=args.ui,
        )
        rc = runner.run() or rc
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
