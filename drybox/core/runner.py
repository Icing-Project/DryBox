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
import pathlib
import random
import sys
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

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
DEFAULT_TICK_MS = 1
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
from drybox.core.adapter_registry import load_adapter_class
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

@dataclass
class AudioFlow:
    src: Any
    dst: Any
    tx_side: str
    rx_side: str
    label: str
    vocoder: Optional[Any] = None
    channel: Optional[Any] = None

@dataclass
class ByteFlow:
    bearer: DatagramBearer
    frag: Optional[SARFragmenter]
    reasm: Optional[SARReassembler]
    src: Any
    dst: Any
    cap_side: str
    metrics_side: str
    side_label: str

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
        cls = load_adapter_class(spec)
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
    
    # Helpers
    def _safe_call(self, label: str, fn, *args, **kwargs):
        """
        Helper to call adapter methods and catch exceptions; returns None on error.
        """
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            print(f"[ERROR] {label}: {e}", file=sys.stderr)
            return None

    def _apply_vocoder_and_loss(self, pcm_in, flow: AudioFlow):
        """
        Apply vocoder encode/decode/process and simulate packet loss per bearer loss_rate.
        Returns pcm_processed and optionally writes DROP metric if loss occurs.
        """
        pcm_processed = pcm_in
        if flow.vocoder is None:
            return pcm_processed

        loss_rate = self.bearer_params.get("loss_rate", 0.0)
        if self.rng.random() < loss_rate:
            # Frame lost - PLC
            pcm_processed = flow.vocoder.process_frame(None)
            self.metrics.write_metric(
                t_ms=self.t_ms,
                side=flow.rx_side,
                layer=LAYER_AUDIOBLOCK,
                event=EVENT_DROP,
                per=1.0,  # Packet error rate = 1 for this frame
            )
        else:
            bitstream = flow.vocoder.encode(pcm_processed)
            pcm_processed = flow.vocoder.decode(bitstream)
            pcm_processed = flow.vocoder.process_frame(pcm_processed)

        return pcm_processed

    def _write_audio_tx_rx_metrics(self, tx_side: str, rx_side: str, rtt_est: float):
        # Keep same metric keys as original
        self.metrics.write_metric(
            t_ms=self.t_ms, side=tx_side, layer=LAYER_AUDIOBLOCK, event=EVENT_TX,
            rtt_ms_est=float(rtt_est)
        )
        self.metrics.write_metric(
            t_ms=self.t_ms, side=rx_side, layer=LAYER_AUDIOBLOCK, event=EVENT_RX,
            latency_ms=0.0
        )

    def _process_audio_direction(self, flow: AudioFlow, rtt_est: float):
        pcm = self._safe_call(f"{flow.label} audio pull", flow.src.pull_tx_block, self.t_ms)
        if pcm is None or pcm.size == 0:
            return

        pcm_processed = pcm

        # Apply channel
        if flow.channel is not None:
            pcm_processed = flow.channel.apply(pcm)
            if hasattr(flow.channel, "get_estimated_snr"):
                snr_est = flow.channel.get_estimated_snr(pcm, pcm_processed)
                self.metrics.write_metric(
                    t_ms=self.t_ms, side=flow.rx_side,
                    layer=LAYER_AUDIOBLOCK, event=EVENT_RX,
                    snr_db_est=snr_est,
                )

        # Apply vocoder + loss
        pcm_processed = self._apply_vocoder_and_loss(pcm_processed, flow)

        # Deliver
        self._safe_call(f"{flow.label} audio push", flow.dst.push_rx_block, pcm_processed, self.t_ms)

        # Metrics
        self._write_audio_tx_rx_metrics(flow.tx_side, flow.rx_side, rtt_est)
    
    def _poll_and_send_bytemode(self, flow: ByteFlow, rtt_est: float, budget_per_tick: int):
        """
        Poll flow.src.poll_link_tx, normalize SDUs, fragment if needed, and send via flow.bearer.
        """
        res = self._safe_call(f"{flow.side_label} poll_link_tx", flow.src.poll_link_tx, budget_per_tick)
        if not res:
            return

        try:
            sdus: List[bytes] = [
                b if isinstance(b, (bytes, bytearray)) else b[0] for b in res
            ]
        except Exception:
            sdus = []

        for sdu in sdus:
            payloads = [sdu]
            if flow.frag is not None:
                payloads = flow.frag.fragment(sdu)
            for p in payloads:
                flow.bearer.send(p, now_ms=self.t_ms)
                self.cap.write(
                    t_ms=self.t_ms,
                    side=flow.cap_side,
                    layer=LAYER_BEARER,
                    event=EVENT_TX,
                    data=bytes(p),
                )
                self.metrics.write_metric(
                    t_ms=self.t_ms,
                    side=flow.cap_side,
                    layer=LAYER_BEARER,
                    event=EVENT_TX,
                    rtt_ms_est=float(rtt_est),
                )
        
    def _deliver_bearer_to_adapter(self, dat, flow: ByteFlow):
        """
        Deliver a datagram from flow.bearer to flow.dst (via optional reassembly).
        """
        self.cap.write(
            t_ms=self.t_ms,
            side=flow.cap_side,
            layer=LAYER_BEARER,
            event=EVENT_RX,
            data=bytes(dat.payload),
        )
        lat = float(self.t_ms - dat.sent_ms)
        sdu: Optional[bytes] = dat.payload
        if flow.reasm is not None:
            sdu = flow.reasm.push_fragment(dat.payload, now_ms=self.t_ms)

        if sdu is not None and hasattr(flow.dst, "on_link_rx"):
            flow.dst.on_link_rx(sdu)
            st = flow.bearer.stats()
            self.metrics.write_metric(
                t_ms=self.t_ms,
                side=flow.metrics_side,
                layer=LAYER_BYTELINK,
                event=EVENT_RX,
                latency_ms=lat,
                jitter_ms=st.jitter_ms,
                loss_rate=st.loss_rate,
                reorder_rate=st.reorder_rate,
            )

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

        # 1) Configure bearer (translate 'network' => bearer type + params)
        # Schema: network: { bearer: "volte_evs", latency_ms: 20, ... }
        network_cfg = dict(self.scenario.network or {})
        bearer_type = network_cfg.get("bearer", "volte_evs")
        # params are everything in network except the 'bearer' key
        bearer_params = {k: v for k, v in network_cfg.items() if k != "bearer"}

        # store for helpers (loss_rate, latency, mtu lookup)
        self.bearer_type = bearer_type
        self.bearer_params = bearer_params

        bearer_l2r: DatagramBearer = make_bearer(bearer_type, bearer_params, self.rng)
        bearer_r2l: DatagramBearer = make_bearer(bearer_type, bearer_params, self.rng)


        # 2) SAR-lite si MTU < SDU_MAX
        sdu_max = int(left_caps.get("sdu_max_bytes", DEFAULT_SDU_MAX))
        mtu = int(self.bearer_params.get("mtu_bytes", sdu_max))
        sar_active = mtu < sdu_max
        frag_l2r = SARFragmenter(mtu_bytes=mtu) if sar_active else None
        frag_r2l = SARFragmenter(mtu_bytes=mtu) if sar_active else None

        # 3) Channel setup (Mode B only)
        # In schema, channel config lives in adapter 'modem' (left/right). We'll prefer left.modem.
        channel = None
        left_modem_cfg = dict(self.scenario.left.get("modem", {}) or {})
        # If left.modem empty, fallback to right.modem
        if not left_modem_cfg:
            left_modem_cfg = dict(self.scenario.right.get("modem", {}) or {})

        channel_type = left_modem_cfg.get("channel_type")
        if self.scenario.mode == "audio" and channel_type:
            if channel_type == "awgn" and AWGNChannel:
                snr_db = left_modem_cfg.get("snr_db", 20.0)
                channel = AWGNChannel(snr_db, seed=self.seed)
            elif channel_type in ["fading", "rayleigh"] and RayleighFadingChannel:
                snr_db = left_modem_cfg.get("snr_db", 20.0)
                fd_hz = left_modem_cfg.get("doppler_hz", 50.0)
                L = left_modem_cfg.get("num_paths", 8)
                channel = RayleighFadingChannel(snr_db, fd_hz, L, seed=self.seed)

        
        # 4) Vocoder setup (Mode B only)
        vocoder_l2r = None
        vocoder_r2l = None
        left_modem_cfg = dict(self.scenario.left.get("modem", {}) or {})
        right_modem_cfg = dict(self.scenario.right.get("modem", {}) or {})

        # prefer explicit vocoder type set in modem config
        vocoder_type = left_modem_cfg.get("vocoder") or right_modem_cfg.get("vocoder")
        if self.scenario.mode == "audio" and vocoder_type and create_vocoder:
            vad_dtx = left_modem_cfg.get("vad_dtx", False) or right_modem_cfg.get("vad_dtx", False)
            vocoder_l2r = create_vocoder(vocoder_type, vad_dtx, seed=self.seed)
            vocoder_r2l = create_vocoder(vocoder_type, vad_dtx, seed=self.seed + 1)

        
        # 5) Réassemblage (timeout = 2×RTT_est ; RTT_est ~ 2×latency_ms si fourni)
        lat_ms = int(self.bearer_params.get("latency_ms", 60))
        rtt_est = max(1, 2 * lat_ms)
        reasm_r2l = SARReassembler(rtt_estimate_ms=2 * rtt_est, expect_header=sar_active)  # R->L
        reasm_l2r = SARReassembler(rtt_estimate_ms=2 * rtt_est, expect_header=sar_active)  # L->R

        # 6) Boucle
        duration = int(self.scenario.duration_ms)
        budget_per_tick = 64  # SDUs max par tick
        last_ui_print = -10_000

        # fenêtres goodput (1 s)
        bytes_rx_l = 0
        bytes_rx_r = 0
        window_start_ms = 0
        
        # --- Byte flows (mode A) ---
        flows_byte = [
            ByteFlow(
                bearer=bearer_l2r,
                frag=frag_l2r,
                reasm=reasm_l2r,
                src=left,
                dst=right,
                cap_side="L",
                metrics_side="R",
                side_label="LEFT",
            ),
            ByteFlow(
                bearer=bearer_r2l,
                frag=frag_r2l,
                reasm=reasm_r2l,
                src=right,
                dst=left,
                cap_side="R",
                metrics_side="L",
                side_label="RIGHT",
            ),
        ]

        # --- Audio flows (mode B) ---
        flows_audio = [
            AudioFlow(
                src=left,
                dst=right,
                tx_side="L",
                rx_side="R",
                label="L->R",
                vocoder=vocoder_l2r,
                channel=channel,
            ),
            AudioFlow(
                src=right,
                dst=left,
                tx_side="R",
                rx_side="L",
                label="R->L",
                vocoder=vocoder_r2l,
                channel=channel,
            ),
        ]

        try:
            while self.t_ms <= duration:
                # (1) Ticks avant toute I/O
                for a in (left, right):
                    if hasattr(a, "on_timer"):
                        a.on_timer(self.t_ms)  # type: ignore[attr-defined]

                # (2) Mode-specific I/O et Livraison via bearer L->R R->L
                if self.scenario.mode == "byte":
                    # Mode A: ByteLink
                    for flow in flows_byte:
                        if hasattr(flow.src, "poll_link_tx"):
                            self._poll_and_send_bytemode(flow, rtt_est, budget_per_tick)
                        for dat in flow.bearer.poll_deliver(self.t_ms):
                            self._deliver_bearer_to_adapter(dat, flow)

                elif self.scenario.mode == "audio":
                    # Mode B: AudioBlock
                    if np is None:
                        raise SystemExit("Mode B (audio) requires numpy. Install with `pip install numpy`.")
                    for flow in flows_audio:
                        if hasattr(flow.src, "pull_tx_block") and hasattr(flow.dst, "push_rx_block"):
                            self._process_audio_direction(flow, rtt_est)

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
    Use 'network' + left/right per schema (not legacy bearer/channel/vocoder attrs).
    """
    doc = {
        "mode": scen.mode,
        "duration_ms": scen.duration_ms,
        "seed": scen.seed,
        "network": dict(scen.network) if scen.network is not None else {},
        "left": dict(scen.left) if scen.left is not None else {},
        "right": dict(scen.right) if scen.right is not None else {},
        "cfo_hz": scen.cfo_hz,
        "ppm": scen.ppm,
        "crypto": dict(scen.crypto or {}),
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
