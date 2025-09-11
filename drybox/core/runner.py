# drybox/core/runner.py
# MIT License
# DryBox Runner v1 — boucle de simulation déterministe + I/O adaptateurs Nade
# - Tick logique (10 ms par défaut), on_timer() avant I/O
# - Mode A (ByteLink) opérationnel (Mode B: hook réservé)
# - Scénarios via résolveur centralisé (A2) + sweep
# - SAR-lite (3 B) côté DryBox si MTU < SDU_MAX
# - Sorties extraites (A1): metrics.csv, events.jsonl, capture .dbxcap

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # PyYAML
except ImportError as e:
    raise SystemExit(
        "PyYAML is required. Install with `uv add pyyaml` or `pip install pyyaml`."
    ) from e

try:
    import numpy as np
except ImportError:
    np = None  # Mode B will require numpy

# --- Constantes / Defaults (brief v1) ---
DEFAULT_TICK_MS = 10
DEFAULT_SEED = 0
DEFAULT_SDU_MAX = 1024  # avant fragmentation SAR
DEFAULT_MODE = "audio"  # défaut global v1 (Mode B), ByteLink reste supporté

# --- Layers/events (sémantique simple) ---
LAYER_BYTELINK = "bytelink"
LAYER_BEARER = "bearer"
LAYER_AUDIOBLOCK = "audioblock"
EVENT_TX = "tx"
EVENT_RX = "rx"
EVENT_DROP = "drop"
EVENT_TICK = "tick"

# --- Dépendances locales ---
from drybox.core.metrics import MetricsWriter  # A1
from drybox.core.capture import DbxCapWriter  # A1
from drybox.core.scenario import (  # A2
    ScenarioResolved,
)

from drybox.net.bearers import (
    DatagramBearer,
    make_bearer,
    BearerStatsSnapshot,
)
from drybox.net.sar_lite import SARFragmenter, SARReassembler

from drybox.core.crypto_keys import resolve_keypairs, key_id

# Channel imports (conditionally loaded)
try:
    from drybox.radio.channel_awgn import AWGNChannel
except ImportError:
    AWGNChannel = None

try:
    from drybox.radio.channel_fading import RayleighFadingChannel
except ImportError:
    RayleighFadingChannel = None

try:
    from drybox.radio.vocoder_models import create_vocoder
except ImportError:
    create_vocoder = None


# --------- Utils: chargement adaptateurs ----------
def _load_class_from_path(spec: str):
    """
    Charge une classe à partir d'une spéc 'path/to/module.py:ClassName'.
    Pas de cache global -> isolation simple entre runs.
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


# --------- Contexte adaptateur ----------
class AdapterCtx:
    """
    Contexte minimal stable v1 pour les adaptateurs.
    - now_ms() : horloge logique
    - emit_event(type, payload) : vers events.jsonl
    - side: "L" | "R"
    - rng: générateur déterministe côté runner
    - config: dict léger (tick_ms, mode, sdu_max_bytes, seed, side)
    """

    def __init__(self, *, side: str, rng: random.Random, get_time_ms, emit_event, config: Dict[str, Any]):
        self.side = side
        self.rng = rng
        self._get_time_ms = get_time_ms
        self._emit_event = emit_event
        self.config = config

    def now_ms(self) -> int:
        return self._get_time_ms()

    def emit_event(self, typ: str, payload: Dict[str, Any]) -> None:
        self._emit_event(self.side, typ, payload)


# --------- Runner ----------
class Runner:
    def __init__(
            self,
            *,
            scenario: ScenarioResolved,
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

        # RNG global seedé (déterminisme)
        self.rng = random.Random(seed)

        # Sorties (A1)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = MetricsWriter(self.out_dir / "metrics.csv", self.out_dir / "events.jsonl")
        self.cap = DbxCapWriter(self.out_dir / "capture.dbxcap")

        # Horloge logique
        self.t_ms: int = 0

    # --------- Chargement / lifecycle ----------
    def _load_adapter(self, spec: str, side: str, crypto_cfg: Dict[str, Any]):
        cls = _load_class_from_path(spec)
        inst = cls()

        # Découverte / capabilities (facultatif)
        caps: Dict[str, Any] = {}
        if hasattr(inst, "nade_capabilities"):
            try:
                caps = inst.nade_capabilities()  # type: ignore[attr-defined]
            except Exception:
                caps = {}

        # Initialisation lato sensu (init + start)
        cfg = {
            "tick_ms": self.tick_ms,
            "side": side,
            "seed": self.seed,
            "mode": self.scenario.mode,
            "sdu_max_bytes": DEFAULT_SDU_MAX,  # hint v1; override via capabilities côté adapter si utile
            "out_dir": str(self.out_dir),
            "crypto": crypto_cfg,
        }
        if hasattr(inst, "init"):
            inst.init(cfg)  # type: ignore[attr-defined]

        ctx = AdapterCtx(
            side=side,
            rng=self.rng,
            get_time_ms=lambda: self.t_ms,
            emit_event=lambda side_, typ, payload: self.metrics.write_event(self.t_ms, side_, typ, payload),
            config=cfg,
        )
        if hasattr(inst, "start"):
            inst.start(ctx)  # type: ignore[attr-defined]
        return inst, caps

    def _require_mode_supported(self, caps_left: Dict[str, Any], caps_right: Dict[str, Any]) -> None:
        """
        Si le mode n'est pas supporté par l'un des endpoints → erreur endpoint (exit 3).
        """
        mode = self.scenario.mode
        if mode == "audio":
            ok = caps_left.get("audioblock", True) and caps_right.get("audioblock", True)
        else:
            ok = caps_left.get("bytelink", True) and caps_right.get("bytelink", True)
        if not ok:
            raise SystemExit(3)

    def _dump_pubkeys(self, *, l_pub: bytes, r_pub: bytes, l_prov: str, r_prov: str) -> None:
        """Écrit runs/.../pubkeys.txt (publiques seules) pour faciliter le debug interop."""
        txt = [
            "# DryBox public keys (Ed25519) — DO NOT SHARE PRIVATE KEYS",
            f"L.key_id={key_id(l_pub)}",
            f"L.pub_hex={l_pub.hex()}",
            f"L.provenance={l_prov}",
            f"R.key_id={key_id(r_pub)}",
            f"R.pub_hex={r_pub.hex()}",
            f"R.provenance={r_prov}",
            f"left_adapter={self.left_adapter_spec}",
            f"right_adapter={self.right_adapter_spec}",
            "",
        ]
        (self.out_dir / "pubkeys.txt").write_text("\n".join(txt), encoding="utf-8")

    # --------- Exécution ----------
    def run(self) -> int:

        # --- Résolution des paires de clés ---
        (l_priv, l_pub, l_prov), (r_priv, r_pub, r_prov) = resolve_keypairs(
            scenario_crypto=self.scenario.crypto,
            seed=self.scenario.seed,
            left_spec=self.left_adapter_spec,
            right_spec=self.right_adapter_spec,
        )
        # Dump *publics* uniquement
        self._dump_pubkeys(l_pub=l_pub, r_pub=r_pub, l_prov=l_prov, r_prov=r_prov)

        l_crypto = {
            "type": "ed25519",
            "priv": l_priv,
            "pub": l_pub,
            "peer_pub": r_pub,
            "provenance": l_prov,
            "key_id": key_id(l_pub),
            "peer_key_id": key_id(r_pub),
        }
        r_crypto = {
            "type": "ed25519",
            "priv": r_priv,
            "pub": r_pub,
            "peer_pub": l_pub,
            "provenance": r_prov,
            "key_id": key_id(r_pub),
            "peer_key_id": key_id(l_pub),
        }

        # --- Charge adaptateurs avec crypto cfg ---
        left, left_caps = self._load_adapter(self.left_adapter_spec, "L", l_crypto)
        right, right_caps = self._load_adapter(self.right_adapter_spec, "R", r_crypto)
        self._require_mode_supported(left_caps, right_caps)

        # 1) Configure bearer (toujours présent — même en mode audio pour MTU/tempo)
        bearer_l2r: DatagramBearer = make_bearer(self.scenario.bearer.type, self.scenario.bearer.params, self.rng)
        bearer_r2l: DatagramBearer = make_bearer(self.scenario.bearer.type, self.scenario.bearer.params, self.rng)

        # 2) SAR-lite si MTU < SDU_MAX
        sdu_max = int(left_caps.get("sdu_max_bytes", DEFAULT_SDU_MAX))
        mtu = int(self.scenario.bearer.params.get("mtu_bytes", sdu_max))
        sar_active = mtu < sdu_max
        frag_l2r = SARFragmenter(mtu_bytes=mtu) if sar_active else None
        frag_r2l = SARFragmenter(mtu_bytes=mtu) if sar_active else None

        # 3) Channel setup (Mode B only)
        channel = None
        if self.scenario.mode == "audio" and self.scenario.channel:
            channel_type = self.scenario.channel.get("type")
            if channel_type == "awgn" and AWGNChannel:
                snr_db = self.scenario.channel.get("snr_db", 20.0)
                channel = AWGNChannel(snr_db, seed=self.seed)
            elif channel_type in ["fading", "rayleigh"] and RayleighFadingChannel:
                snr_db = self.scenario.channel.get("snr_db", 20.0)
                fd_hz = self.scenario.channel.get("fd_hz", 50.0)
                L = self.scenario.channel.get("L", 8)
                channel = RayleighFadingChannel(snr_db, fd_hz, L, seed=self.seed)
        
        # 4) Vocoder setup (Mode B only)
        vocoder_l2r = None
        vocoder_r2l = None
        if self.scenario.mode == "audio" and self.scenario.vocoder and create_vocoder:
            vocoder_type = self.scenario.vocoder.get("type")
            if vocoder_type:
                vad_dtx = self.scenario.vocoder.get("vad_dtx", False)
                vocoder_l2r = create_vocoder(vocoder_type, vad_dtx, seed=self.seed)
                vocoder_r2l = create_vocoder(vocoder_type, vad_dtx, seed=self.seed + 1)
        
        # 5) Réassemblage (timeout = 2×RTT_est ; RTT_est ~ 2×latency_ms si fourni)
        lat_ms = int(self.scenario.bearer.params.get("latency_ms", 60))
        rtt_est = max(1, 2 * lat_ms)
        reas_l = SARReassembler(rtt_estimate_ms=2 * rtt_est, expect_header=sar_active)  # R->L
        reas_r = SARReassembler(rtt_estimate_ms=2 * rtt_est, expect_header=sar_active)  # L->R

        # 6) Boucle
        duration = int(self.scenario.duration_ms)
        budget_per_tick = 64  # SDUs max par tick
        last_ui_print = -10_000

        # fenêtres goodput (1 s)
        bytes_rx_l = 0
        bytes_rx_r = 0
        window_start_ms = 0

        try:
            while self.t_ms <= duration:
                # (1) Ticks avant toute I/O
                for a in (left, right):
                    if hasattr(a, "on_timer"):
                        a.on_timer(self.t_ms)  # type: ignore[attr-defined]

                # (2) Mode-specific I/O
                if self.scenario.mode == "byte":
                    # LEFT -> BEARER
                    if hasattr(left, "poll_link_tx"):
                        try:
                            res = left.poll_link_tx(budget_per_tick)  # type: ignore[attr-defined]
                            sdus: List[bytes] = [
                                b if isinstance(b, (bytes, bytearray)) else b[0] for b in (res or [])
                            ]  # type: ignore[index]
                        except Exception:
                            sdus = []
                        for sdu in sdus:
                            payloads = [sdu]
                            if sar_active and frag_l2r is not None:
                                payloads = frag_l2r.fragment(sdu)
                            for p in payloads:
                                bearer_l2r.send(p, now_ms=self.t_ms)
                                self.cap.write(t_ms=self.t_ms, side="L", layer=LAYER_BEARER, event=EVENT_TX,
                                               data=bytes(p))
                                self.metrics.write_metric(
                                    t_ms=self.t_ms, side="L", layer=LAYER_BEARER, event=EVENT_TX,
                                    rtt_ms_est=float(rtt_est)
                                )

                    # RIGHT -> BEARER
                    if hasattr(right, "poll_link_tx"):
                        try:
                            res_r = right.poll_link_tx(budget_per_tick)  # type: ignore[attr-defined]
                            sdus_r: List[bytes] = [
                                b if isinstance(b, (bytes, bytearray)) else b[0] for b in (res_r or [])
                            ]  # type: ignore[index]
                        except Exception:
                            sdus_r = []
                        for sdu in sdus_r:
                            payloads = [sdu]
                            if sar_active and frag_r2l is not None:
                                payloads = frag_r2l.fragment(sdu)
                            for p in payloads:
                                bearer_r2l.send(p, now_ms=self.t_ms)
                                self.cap.write(t_ms=self.t_ms, side="R", layer=LAYER_BEARER, event=EVENT_TX,
                                               data=bytes(p))
                                self.metrics.write_metric(
                                    t_ms=self.t_ms, side="R", layer=LAYER_BEARER, event=EVENT_TX,
                                    rtt_ms_est=float(rtt_est)
                                )

                    # (3) Livraison via bearer L->R
                    for dat in bearer_l2r.poll_deliver(self.t_ms):
                        self.cap.write(t_ms=self.t_ms, side="L", layer=LAYER_BEARER, event=EVENT_RX,
                                       data=bytes(dat.payload))
                        lat = float(self.t_ms - dat.sent_ms)
                        sdu: Optional[bytes] = dat.payload
                        if sar_active:
                            sdu = reas_r.push_fragment(dat.payload, now_ms=self.t_ms)
                        if sdu is not None and hasattr(right, "on_link_rx"):
                            right.on_link_rx(sdu)  # type: ignore[attr-defined]
                            st = bearer_l2r.stats()
                            self.metrics.write_metric(
                                t_ms=self.t_ms,
                                side="R",
                                layer=LAYER_BYTELINK,
                                event=EVENT_RX,
                                latency_ms=lat,
                                jitter_ms=st.jitter_ms,
                                loss_rate=st.loss_rate,
                                reorder_rate=st.reorder_rate,
                            )
                            bytes_rx_r += len(sdu)

                    # (4) Livraison via bearer R->L
                    for dat in bearer_r2l.poll_deliver(self.t_ms):
                        self.cap.write(t_ms=self.t_ms, side="R", layer=LAYER_BEARER, event=EVENT_RX,
                                       data=bytes(dat.payload))
                        lat = float(self.t_ms - dat.sent_ms)
                        sdu: Optional[bytes] = dat.payload
                        if sar_active:
                            sdu = reas_l.push_fragment(dat.payload, now_ms=self.t_ms)
                        if sdu is not None and hasattr(left, "on_link_rx"):
                            left.on_link_rx(sdu)  # type: ignore[attr-defined]
                            st = bearer_r2l.stats()
                            self.metrics.write_metric(
                                t_ms=self.t_ms,
                                side="L",
                                layer=LAYER_BYTELINK,
                                event=EVENT_RX,
                                latency_ms=lat,
                                jitter_ms=st.jitter_ms,
                                loss_rate=st.loss_rate,
                                reorder_rate=st.reorder_rate,
                            )
                            bytes_rx_l += len(sdu)

                elif self.scenario.mode == "audio":
                    # Mode B: AudioBlock
                    if np is None:
                        raise SystemExit("Mode B (audio) requires numpy. Install with `pip install numpy`.")
                    
                    # Check if both adapters support AudioBlock
                    if hasattr(left, "pull_tx_block") and hasattr(right, "push_rx_block"):
                        # L->R audio flow
                        try:
                            pcm_l = left.pull_tx_block(self.t_ms)  # type: ignore[attr-defined]
                            if pcm_l is not None and len(pcm_l) > 0:
                                # Apply channel effects if configured
                                pcm_processed = pcm_l
                                if channel is not None:
                                    pcm_processed = channel.apply(pcm_l)
                                    # Estimate SNR for metrics
                                    if hasattr(channel, 'get_estimated_snr'):
                                        snr_est = channel.get_estimated_snr(pcm_l, pcm_processed)
                                        self.metrics.write_metric(
                                            t_ms=self.t_ms, side="R", layer=LAYER_AUDIOBLOCK, event=EVENT_RX,
                                            snr_db_est=snr_est
                                        )
                                # Apply vocoder if configured
                                if vocoder_l2r is not None:
                                    # Simulate packet loss based on bearer loss rate
                                    loss_rate = self.scenario.bearer.params.get("loss_rate", 0.0)
                                    if self.rng.random() < loss_rate:
                                        # Frame lost - apply PLC
                                        pcm_processed = vocoder_l2r.process_frame(None)
                                        self.metrics.write_metric(
                                            t_ms=self.t_ms, side="R", layer=LAYER_AUDIOBLOCK, event=EVENT_DROP,
                                            per=1.0  # Packet error rate = 1 for this frame
                                        )
                                    else:
                                        # Normal processing
                                        bitstream = vocoder_l2r.encode(pcm_processed)
                                        pcm_processed = vocoder_l2r.decode(bitstream)
                                        pcm_processed = vocoder_l2r.process_frame(pcm_processed)
                                
                                right.push_rx_block(pcm_processed, self.t_ms)  # type: ignore[attr-defined]
                                
                                # Metrics
                                self.metrics.write_metric(
                                    t_ms=self.t_ms, side="L", layer=LAYER_AUDIOBLOCK, event=EVENT_TX,
                                    rtt_ms_est=float(rtt_est)
                                )
                                self.metrics.write_metric(
                                    t_ms=self.t_ms, side="R", layer=LAYER_AUDIOBLOCK, event=EVENT_RX,
                                    latency_ms=0.0  # Direct passthrough for now
                                )
                        except Exception as e:
                            print(f"[ERROR] L->R audio: {e}", file=sys.stderr)
                    
                    if hasattr(right, "pull_tx_block") and hasattr(left, "push_rx_block"):
                        # R->L audio flow
                        try:
                            pcm_r = right.pull_tx_block(self.t_ms)  # type: ignore[attr-defined]
                            if pcm_r is not None and len(pcm_r) > 0:
                                # Apply channel effects if configured
                                pcm_processed = pcm_r
                                if channel is not None:
                                    pcm_processed = channel.apply(pcm_r)
                                    # Estimate SNR for metrics
                                    if hasattr(channel, 'get_estimated_snr'):
                                        snr_est = channel.get_estimated_snr(pcm_r, pcm_processed)
                                        self.metrics.write_metric(
                                            t_ms=self.t_ms, side="L", layer=LAYER_AUDIOBLOCK, event=EVENT_RX,
                                            snr_db_est=snr_est
                                        )
                                # Apply vocoder if configured
                                if vocoder_r2l is not None:
                                    # Simulate packet loss based on bearer loss rate
                                    loss_rate = self.scenario.bearer.params.get("loss_rate", 0.0)
                                    if self.rng.random() < loss_rate:
                                        # Frame lost - apply PLC
                                        pcm_processed = vocoder_r2l.process_frame(None)
                                        self.metrics.write_metric(
                                            t_ms=self.t_ms, side="L", layer=LAYER_AUDIOBLOCK, event=EVENT_DROP,
                                            per=1.0  # Packet error rate = 1 for this frame
                                        )
                                    else:
                                        # Normal processing
                                        bitstream = vocoder_r2l.encode(pcm_processed)
                                        pcm_processed = vocoder_r2l.decode(bitstream)
                                        pcm_processed = vocoder_r2l.process_frame(pcm_processed)
                                
                                left.push_rx_block(pcm_processed, self.t_ms)  # type: ignore[attr-defined]
                                
                                # Metrics
                                self.metrics.write_metric(
                                    t_ms=self.t_ms, side="R", layer=LAYER_AUDIOBLOCK, event=EVENT_TX,
                                    rtt_ms_est=float(rtt_est)
                                )
                                self.metrics.write_metric(
                                    t_ms=self.t_ms, side="L", layer=LAYER_AUDIOBLOCK, event=EVENT_RX,
                                    latency_ms=0.0  # Direct passthrough for now
                                )
                        except Exception as e:
                            print(f"[ERROR] R->L audio: {e}", file=sys.stderr)

                # (5) Goodput fenêtré (1 s)
                if self.scenario.mode == "byte" and self.t_ms - window_start_ms >= 1000:
                    dur = max(1, self.t_ms - window_start_ms)
                    g_l = (bytes_rx_l * 8) / dur * 1000.0
                    g_r = (bytes_rx_r * 8) / dur * 1000.0
                    self.metrics.write_metric(t_ms=self.t_ms, side="L", layer=LAYER_BYTELINK, event=EVENT_TICK,
                                              goodput_bps=g_l)
                    self.metrics.write_metric(t_ms=self.t_ms, side="R", layer=LAYER_BYTELINK, event=EVENT_TICK,
                                              goodput_bps=g_r)
                    bytes_rx_l = 0
                    bytes_rx_r = 0
                    window_start_ms = self.t_ms

                # (6) UI minimale (stderr)
                if self.ui_enabled and (self.t_ms - last_ui_print) >= 1000:
                    if self.scenario.mode == "byte":
                        s_l: BearerStatsSnapshot = bearer_l2r.stats()
                        s_r: BearerStatsSnapshot = bearer_r2l.stats()
                        print(
                            f"[{self.t_ms:6d} ms] "
                            f"L->R loss={s_l.loss_rate:.3f} reord={s_l.reorder_rate:.3f} jitter={s_l.jitter_ms:.1f}ms | "
                            f"R->L loss={s_r.loss_rate:.3f} reord={s_r.reorder_rate:.3f} jitter={s_r.jitter_ms:.1f}ms",
                            file=sys.stderr,
                        )
                    elif self.scenario.mode == "audio":
                        print(
                            f"[{self.t_ms:6d} ms] Mode B Audio - Direct passthrough active",
                            file=sys.stderr,
                        )
                    last_ui_print = self.t_ms

                # (7) Horloge
                self.t_ms += self.tick_ms

            return 0  # Évaluation de seuils: module dédié (à venir A1/A6)
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
    p.add_argument("--plot", action="store_true", help="Generate plots after simulation completes")
    p.add_argument("--sweep-parallel", type=int, default=1, help="(reserved) parallelism per sweep value")
    return p.parse_args(argv)


def _write_resolved_yaml(path: pathlib.Path, scen: ScenarioResolved) -> None:
    """
    Écrit le scénario résolu utilisé pour le run (toujours émis).
    """
    doc = {
        "mode": scen.mode,
        "duration_ms": scen.duration_ms,
        "seed": scen.seed,
        "bearer": {"type": scen.bearer.type, **scen.bearer.params},
        "channel": scen.channel,
        "vocoder": scen.vocoder,
        "cfo_hz": scen.cfo_hz,
        "ppm": scen.ppm,
    }
    with open(path, "w", encoding="utf-8") as fp:
        yaml.safe_dump(doc, fp, sort_keys=False)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    scen_path = pathlib.Path(args.scenario).resolve()
    try:
        base = ScenarioResolved.from_yaml(scen_path)  # A2: validation + défauts centralisés
    except Exception as e:
        # YAML invalide ⇒ exit 4 (A2)
        sys.stderr.write(f"[scenario] invalid: {e}\n")
        raise SystemExit(4)

    # Sweep (A2): dupliquer par valeur (snr_db, etc.)
    clones: List[Tuple[str, ScenarioResolved]] = ScenarioResolved.expand_sweep(base)

    root_out = pathlib.Path(args.out).resolve()
    rc = 0
    for suffix, scen in clones:
        out_dir = root_out if not suffix else root_out / suffix
        out_dir.mkdir(parents=True, exist_ok=True)
        # Toujours écrire le scénario résolu pour chaque run
        _write_resolved_yaml(out_dir / "scenario.resolved.yaml", scen)

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
        
        # Generate plots if requested
        if args.plot:
            try:
                import subprocess
                plot_cmd = [
                    sys.executable, "-m", "tools.plot_timeline",
                    str(out_dir),
                    "--type", "all"
                ]
                subprocess.run(plot_cmd, check=True)
                print(f"[plot] Generated plots in: {out_dir}/plots/")
            except Exception as e:
                sys.stderr.write(f"[plot] Failed to generate plots: {e}\n")
    
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
