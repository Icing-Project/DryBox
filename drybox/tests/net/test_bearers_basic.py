# tests/net/test_bearers_basic.py
# MIT License
from __future__ import annotations

import statistics
import random

from drybox.net.bearers import TelcoVolteEvs, TelcoCsGsm


def _simulate_and_collect_latencies(bearer, duration_ms: int, send_period_ms: int = 20):
    """
    Envoie un PDU toutes les send_period_ms, appelle poll_deliver() à 1 ms
    et renvoie la liste des latences (deliver_ms - sent_ms) observées.
    """
    lats = []
    for t in range(0, duration_ms + 1):
        if (t % send_period_ms) == 0:
            bearer.send(b"x", now_ms=t)
        for it in bearer.poll_deliver(now_ms=t):
            lats.append(it.deliver_ms - it.sent_ms)
    return lats


def test_volte_latency_mean_close_and_jitter_positive():
    """
    VoLTE/EVS mock:
      - latence moyenne ≈ consigne (jitter centré), sur fenêtre suffisante
      - jitter > 0 si configuré
    """
    rng = random.Random(1234)
    params = {
        "latency_ms": 60,
        "jitter_ms": 20,
        "loss_rate": 0.0,
        "reorder_rate": 0.0,
        "mtu_bytes": 96,
        "frame_ms": 20,
        # Stabilise le GE: rester en "good"
        "ge_p_good_bad": 0.0,
        "ge_p_bad_good": 1.0,
    }
    b = TelcoVolteEvs(params, rng)
    lats = _simulate_and_collect_latencies(b, duration_ms=20_000, send_period_ms=20)

    assert len(lats) > 200  # assez d'échantillons
    mean_lat = statistics.mean(lats)
    # Centré autour de 60 ms (gaussien tronqué ±3σ) → marge prudente
    assert 57.0 <= mean_lat <= 63.0

    # Jitter RFC3550-like doit être > 0 si jitter_ms > 0
    stats = b.stats()
    assert stats.jitter_ms > 0.0


def test_cs_gsm_no_reorder():
    """
    CS-GSM: pas de réordonnancement (transport circuit).
    On neutralise les événements 'handover' pour éviter tout inversions d'ordre.
    """
    rng = random.Random(42)
    params = {
        "latency_ms": 120,
        "burst_loss_rate": 0.0,          # pas de burst
        "burst_ms_mean": 10_000_000,     # inactif
        "handover_interval_ms_mean": 10_000_000,  # pas de HO sur la durée du test
        "amr_mode_switch": False,
    }
    b = TelcoCsGsm(params, rng)
    _ = _simulate_and_collect_latencies(b, duration_ms=10_000, send_period_ms=20)

    stats = b.stats()
    assert stats.reorder_rate == 0.0


def test_bearer_determinism_with_seed():
    """
    Même seed → même chronologie de livraisons (déterminisme).
    """
    params = {
        "latency_ms": 60,
        "jitter_ms": 10,
        "loss_rate": 0.0,
        "reorder_rate": 0.0,
        "mtu_bytes": 1200,
        "frame_ms": 20,
        "ge_p_good_bad": 0.0,
        "ge_p_bad_good": 1.0,
    }

    def run(seed):
        rng = random.Random(seed)
        b = TelcoVolteEvs(params, rng)
        lats = _simulate_and_collect_latencies(b, duration_ms=5_000, send_period_ms=20)
        # collecter les timestamps d'arrivée pour comparaison stricte
        # (on reconstruit à partir des latences et de la cadence)
        return lats

    ref = run(123456)
    again = run(123456)
    diff = run(654321)

    assert again == ref
    assert diff != ref
