# drybox/net/bearers.py
# MIT License
# Datagram Bearers (Mode A + transport commun)
# - telco_volte_evs : latence+jitter+pertes+réordonnancement + Gilbert–Elliott
# - telco_cs_gsm    : bursts de pertes + "handover" périodique
# - telco_pstn_g711 : placeholder datagramme (MTU large, pas de réordonnancement)
# - ott_udp         : simple IP: latence+jitter+pertes+réordres
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class _InFlight:
    payload: bytes
    sent_ms: int
    deliver_ms: int
    seq: int


@dataclass
class BearerStatsSnapshot:
    loss_rate: float
    reorder_rate: float
    jitter_ms: float


class DatagramBearer:
    """
    Modèle de transport "datagramme".
    - send(payload, now_ms) : schedule (pertes/jitter/latence/réordres)
    - poll_deliver(now_ms) : délivre les PDUs arrivés à échéance
    - stats() : snapshot courants
    """

    def __init__(self, *, rng: random.Random, mtu_bytes: int, latency_ms: int):
        self.rng = rng
        self.mtu_bytes = mtu_bytes
        self.latency_ms = latency_ms
        self._queue: List[_InFlight] = []
        self._drops = 0
        self._tx = 0
        self._reorders = 0
        self._last_delivered_seq: Optional[int] = None
        self._seq_ctr = 0
        # Jitter RFC3550-like (variation du transit)
        self._last_transit: Optional[int] = None
        self._jitter: float = 0.0

    # ---- paramètres volatiles selon bearer concret ----
    def _should_drop(self) -> bool:
        return False

    def _extra_delay_ms(self) -> int:
        return 0

    def _maybe_reorder(self, item: _InFlight) -> None:
        # by default: rien
        return

    # ----------------------------------------------------
    def send(self, payload: bytes, *, now_ms: int) -> None:
        self._tx += 1
        if self._should_drop():
            self._drops += 1
            return
        base = self.latency_ms
        extra = self._extra_delay_ms()
        deliver = max(now_ms + base + extra, now_ms)
        item = _InFlight(payload=bytes(payload), sent_ms=now_ms, deliver_ms=deliver, seq=self._seq_ctr)
        self._seq_ctr = (self._seq_ctr + 1) & 0x7FFFFFFF
        # Optionnel réordonnancement
        self._maybe_reorder(item)
        self._queue.append(item)

    def poll_deliver(self, now_ms: int) -> List[_InFlight]:
        out: List[_InFlight] = []
        keep: List[_InFlight] = []
        for it in self._queue:
            if it.deliver_ms <= now_ms:
                out.append(it)
                # Stats reorder:
                if self._last_delivered_seq is not None and it.seq < self._last_delivered_seq:
                    self._reorders += 1
                self._last_delivered_seq = it.seq
                # Jitter (diff des transits)
                transit = it.deliver_ms - it.sent_ms
                if self._last_transit is not None:
                    d = abs(transit - self._last_transit)
                    self._jitter += (d - self._jitter) / 16.0
                self._last_transit = transit
            else:
                keep.append(it)
        # Stable order among due items (simulate same-timestamp reorders already accounted)
        out.sort(key=lambda x: x.deliver_ms)
        self._queue = keep
        return out

    def stats(self) -> BearerStatsSnapshot:
        loss = (self._drops / self._tx) if self._tx else 0.0
        reord = (self._reorders / max(1, self._tx - self._drops)) if self._tx else 0.0
        return BearerStatsSnapshot(loss_rate=loss, reorder_rate=reord, jitter_ms=self._jitter)


# -------------------- VOLTE / EVS --------------------
class TelcoVolteEvs(DatagramBearer):
    """
    Paramètres:
      latency_ms, jitter_ms, loss_rate, reorder_rate,
      ge_p_good_bad, ge_p_bad_good, mtu_bytes, frame_ms (def=20)
    - Pertes: Gilbert-Elliott (état Good/Bad) + loss_rate de base
    - Jitter: gaussien tronqué
    - Réordre: probabilité par paquet -> retard d'un frame supplémentaire pour inverser l'ordre
    """
    def __init__(self, params: Dict[str, Any], rng: random.Random):
        mtu = int(params.get("mtu_bytes", 1024))
        super().__init__(rng=rng, mtu_bytes=mtu, latency_ms=int(params.get("latency_ms", 60)))
        self.jitter_ms = int(params.get("jitter_ms", 20))
        self.loss_rate = float(params.get("loss_rate", 0.0))
        self.reorder_rate = float(params.get("reorder_rate", 0.0))
        self.frame_ms = int(params.get("frame_ms", 20))
        self.p_gb = float(params.get("ge_p_good_bad", 0.001))
        self.p_bg = float(params.get("ge_p_bad_good", 0.1))
        self._ge_bad = False  # état initial: good

    def _should_drop(self) -> bool:
        # Update GE state
        if self._ge_bad:
            if self.rng.random() < self.p_bg:
                self._ge_bad = False
        else:
            if self.rng.random() < self.p_gb:
                self._ge_bad = True
        p = self.loss_rate + (0.3 if self._ge_bad else 0.0)  # en "bad", +30% pertes
        return self.rng.random() < min(1.0, max(0.0, p))

    def _extra_delay_ms(self) -> int:
        if self.jitter_ms <= 0:
            return 0
        # Gaussien centré, écart-type = jitter/2, tronqué à +-3σ
        sigma = max(1.0, self.jitter_ms / 2.0)
        val = self.rng.gauss(0.0, sigma)
        val = max(-3 * sigma, min(3 * sigma, val))
        return int(round(val))

    def _maybe_reorder(self, item: _InFlight) -> None:
        if self.reorder_rate <= 0:
            return
        if self.rng.random() < self.reorder_rate:
            item.deliver_ms += self.frame_ms  # retarde d'un frame -> possiblement inversé


# -------------------- CS GSM --------------------
class TelcoCsGsm(DatagramBearer):
    """
    Paramètres:
      latency_ms, burst_loss_rate, burst_ms_mean, handover_interval_ms_mean, amr_mode_switch
    - Bursts: alternance périodes "bursting" où perte elevée vs nominal (faible)
    - Réordonnancement: supposé nul (CS circuit)
    """
    def __init__(self, params: Dict[str, Any], rng: random.Random):
        super().__init__(rng=rng, mtu_bytes=1024, latency_ms=int(params.get("latency_ms", 120)))
        self.burst_loss_rate = float(params.get("burst_loss_rate", 0.1))
        self.burst_ms_mean = int(params.get("burst_ms_mean", 100))
        self.ho_interval_mean = int(params.get("handover_interval_ms_mean", 8000))
        self._burst_until_ms: int = -1
        self._next_ho_ms: int = self.ho_interval_mean
        self._now_ms: int = 0

    def _should_drop(self) -> bool:
        # Temps interne approx. (actualisé via send())
        p = self.burst_loss_rate if self._now_ms <= self._burst_until_ms else 0.01
        return self.rng.random() < min(1.0, max(0.0, p))

    def send(self, payload: bytes, *, now_ms: int) -> None:
        self._now_ms = now_ms
        # Déclenche un burst stochastique
        if now_ms > self._burst_until_ms and self.rng.random() < 0.02:
            self._burst_until_ms = now_ms + max(20, int(self.rng.expovariate(1.0 / max(1, self.burst_ms_mean))))
        # Handover -> spike de latence ponctuel
        if now_ms >= self._next_ho_ms:
            self.latency_ms += 20  # petit step
            self._next_ho_ms = now_ms + max(1000, int(self.rng.expovariate(1.0 / max(1, self.ho_interval_mean))))
        super().send(payload, now_ms=now_ms)

    def _extra_delay_ms(self) -> int:
        # Pas de jitter marqué en CS, mais on tolère ±5ms
        return int(self.rng.uniform(-5, 5))


# -------------------- PSTN G.711 --------------------
class TelcoPstnG711(DatagramBearer):
    """
    Placeholder datagramme pour PSTN (la chaîne audio réelle sera en Mode B).
    Paramètres:
      latency_ms, (hum / bruit: ignorés ici, pertinents en audio)
    """
    def __init__(self, params: Dict[str, Any], rng: random.Random):
        super().__init__(rng=rng, mtu_bytes=1024, latency_ms=int(params.get("latency_ms", 80)))
        self.jitter_ms = int(params.get("jitter_ms", 5))

    def _extra_delay_ms(self) -> int:
        return int(self.rng.uniform(-self.jitter_ms, self.jitter_ms))


# -------------------- OTT/UDP --------------------
class OttUdp(DatagramBearer):
    """
    Paramètres:
      latency_ms, jitter_ms, loss_rate, reorder_rate, mtu_bytes
    """
    def __init__(self, params: Dict[str, Any], rng: random.Random):
        mtu = int(params.get("mtu_bytes", 1200))
        super().__init__(rng=rng, mtu_bytes=mtu, latency_ms=int(params.get("latency_ms", 40)))
        self.jitter_ms = int(params.get("jitter_ms", 10))
        self.loss_rate = float(params.get("loss_rate", 0.0))
        self.reorder_rate = float(params.get("reorder_rate", 0.0))
        self.frame_ms = int(params.get("frame_ms", 20))

    def _should_drop(self) -> bool:
        return self.rng.random() < self.loss_rate

    def _extra_delay_ms(self) -> int:
        return int(self.rng.gauss(0.0, max(1.0, self.jitter_ms / 2.0)))

    def _maybe_reorder(self, item: _InFlight) -> None:
        if self.rng.random() < self.reorder_rate:
            item.deliver_ms += self.frame_ms


# -------------------- Factory --------------------
def make_bearer(kind: str, params: Dict[str, Any], rng: random.Random) -> DatagramBearer:
    kind = kind.lower()
    if kind in ("telco_volte_evs", "volte_evs", "volte"):
        return TelcoVolteEvs(params, rng)
    if kind in ("telco_cs_gsm", "cs_gsm", "gsm"):
        return TelcoCsGsm(params, rng)
    if kind in ("telco_pstn_g711", "pstn_g711", "pstn"):
        return TelcoPstnG711(params, rng)
    if kind in ("ott_udp", "udp", "ip"):
        return OttUdp(params, rng)
    raise ValueError(f"Unknown bearer type: {kind}")
