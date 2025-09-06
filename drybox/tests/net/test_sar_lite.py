# tests/net/test_sar_lite.py
# MIT License
from __future__ import annotations

import random
from typing import List, Optional

from hypothesis import given, settings, strategies as st, assume

from drybox.net.sar_lite import SARFragmenter, SARReassembler, HEADER_LEN


def _shuffle_deterministic(xs: List[bytes], seed: int) -> List[bytes]:
    xs = list(xs)
    rng = random.Random(seed)
    rng.shuffle(xs)
    return xs


@settings(max_examples=120, deadline=None)
@given(
    sdu=st.binary(min_size=0, max_size=2048),
    mtu=st.integers(min_value=HEADER_LEN + 1, max_value=256),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_sar_identity_reassemble_any_permutation(sdu: bytes, mtu: int, seed: int) -> None:
    """
    Propriété: fragmenter puis réassembler (fragments livrés dans un ordre arbitraire)
    rend exactement l'SDU source.
    Timeout non déclenché (now_ms constant).
    """
    frag = SARFragmenter(mtu_bytes=mtu)
    frags = frag.fragment(sdu)
    # Injection dans un ordre déterministe mais pseudo-aléatoire (stable par seed+mtu+len(sdu))
    order = _shuffle_deterministic(frags, seed ^ len(sdu) ^ mtu)
    reas = SARReassembler(rtt_estimate_ms=10_000, expect_header=True)

    out: Optional[bytes] = None
    for f in order:
        got = reas.push_fragment(f, now_ms=0)
        if got is not None:
            assert out is None, "Réassemblage ne doit se produire qu'une seule fois"
            out = got

    # Cas trivial: si un seul fragment était produit (len(sdu)<=cap),
    # le réassemblage peut se produire dès le premier push.
    assert out == sdu


@st.composite
def _multi_fragment_cases(draw):
    # Garantit ≥ 2 fragments: on choisit sdu_len > (mtu - HEADER_LEN)
    mtu = draw(st.integers(min_value=HEADER_LEN + 4, max_value=128))
    cap = mtu - HEADER_LEN
    # Borne supérieure raisonnable pour rester rapide
    max_len = min(2048, cap * 8 if cap * 8 >= cap + 1 else cap + 1)
    sdu_len = draw(st.integers(min_value=cap + 1, max_value=max_len))
    sdu = draw(st.binary(min_size=sdu_len, max_size=sdu_len))
    seed = draw(st.integers(min_value=0, max_value=2**32 - 1))
    return sdu, mtu, seed

@settings(max_examples=120, deadline=None)
@given(case=_multi_fragment_cases())
def test_sar_partial_loss_timeout_then_clean_abort(case) -> None:
    """
    Propriété: perte d'au moins un fragment => aucun SDU ne doit sortir.
    Puis, après expiration du timeout (~2×RTT_est), le groupe est purgé
    et un fragment tardif isolé ne réassemble pas l'ancien SDU.
    """
    sdu, mtu, seed = case

    frag = SARFragmenter(mtu_bytes=mtu)
    frags = frag.fragment(sdu)
    # Invariant du générateur: on a bien ≥ 2 fragments
    assert len(frags) >= 2

    order = _shuffle_deterministic(frags, seed)
    drop_idx = random.Random(seed ^ 0xA5A5).randrange(len(order))
    missing = order.pop(drop_idx)

    reas = SARReassembler(rtt_estimate_ms=200, expect_header=True)

    # Push de tous les fragments sauf un → jamais de SDU complet
    for t, f in enumerate(order):
        assert reas.push_fragment(f, now_ms=t) is None

    # Avance logique du temps au-delà du timeout pour purger le groupe
    # (push d'un "fragment" invalide (<3B) pour déclencher l'eviction interne)
    assert reas.push_fragment(b"\x00", now_ms=10_000) is None

    # L'arrivée tardive d'un fragment seul ne doit pas réassembler l'ancien SDU
    assert reas.push_fragment(missing, now_ms=10_100) is None



def test_sar_single_fragment_path() -> None:
    """
    Cas bord: len(SDU) <= (MTU-3) => un seul fragment avec last=1.
    """
    mtu = 128
    sdu = b"hello"
    fr = SARFragmenter(mtu_bytes=mtu).fragment(sdu)
    assert len(fr) == 1
    reas = SARReassembler(rtt_estimate_ms=1000, expect_header=True)
    assert reas.push_fragment(fr[0], now_ms=0) == sdu


def test_reassembler_passthrough_when_header_not_expected() -> None:
    """
    Mode pass-through lorsque expect_header=False (utilisé quand SAR n'est pas actif).
    """
    reas = SARReassembler(rtt_estimate_ms=1000, expect_header=False)
    payload = b"\x01\x02\x03\x04\x05"
    assert reas.push_fragment(payload, now_ms=0) == payload
