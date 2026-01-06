# drybox/net/sar_lite.py
# MIT License
# SAR-lite (3 octets): {frag_id:u8, idx:u8, last:u8}
# - Fragmentation si MTU < len(SDU)+3 ; sinon entête unique avec last=1 si SAR actif
# - Réassemblage par (frag_id), timeout = 2 × RTT_est (configurable)
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


HEADER_LEN = 3


def _u8(x: int) -> int:
    return x & 0xFF


class SARFragmenter:
    def __init__(self, *, mtu_bytes: int):
        if mtu_bytes <= HEADER_LEN:
            raise ValueError(f"MTU must be > {HEADER_LEN}, got {mtu_bytes}")
        self.mtu = mtu_bytes
        self._frag_id = 0

    def fragment(self, sdu: bytes) -> list[bytes]:
        """
        Découpe l'SDU en fragments avec en-tête 3B.
        Si un seul fragment, on émet quand même un header (last=1).
        """
        cap = self.mtu - HEADER_LEN
        if len(sdu) <= cap:
            out = [bytes((_u8(self._frag_id), 0, 1)) + sdu]
            self._frag_id = _u8(self._frag_id + 1)
            return out
        # fragments multiples
        out: list[bytes] = []
        fid = self._frag_id
        self._frag_id = _u8(self._frag_id + 1)
        n = (len(sdu) + cap - 1) // cap
        for idx in range(n):
            beg = idx * cap
            end = min(len(sdu), beg + cap)
            last = 1 if idx == (n - 1) else 0
            out.append(bytes((_u8(fid), _u8(idx), _u8(last))) + sdu[beg:end])
        return out


@dataclass
class _Group:
    # premier arrivée -> start_ms (pour timeout)
    start_ms: int
    last_idx: Optional[int] = None
    parts: Dict[int, bytes] = field(default_factory=dict)


class SARReassembler:
    def __init__(self, *, rtt_estimate_ms: int, expect_header: bool):
        self._groups: Dict[int, _Group] = {}
        self._timeout_ms = max(10, rtt_estimate_ms)
        self._expect_header = expect_header

    def push_fragment(self, frag: bytes, *, now_ms: int) -> Optional[bytes]:
        """
        Retourne un SDU complet ou None. Si expect_header=False, passe-through (SDU).
        """
        if not self._expect_header:
            return bytes(frag)

        if len(frag) < HEADER_LEN:
            # fragment invalide -> drop
            return None

        fid = frag[0]
        idx = frag[1]
        last = frag[2]
        payload = frag[HEADER_LEN:]

        # Gère timeouts
        self._evict_timeouts(now_ms)

        grp = self._groups.get(fid)
        if grp is None:
            grp = _Group(start_ms=now_ms)
            self._groups[fid] = grp

        if last == 1:
            grp.last_idx = idx
        # enregistre
        grp.parts[idx] = payload

        # Complet ?
        if grp.last_idx is not None:
            needed = grp.last_idx + 1
            if all(i in grp.parts for i in range(needed)):
                # Ré-assemble
                sdu = b"".join(grp.parts[i] for i in range(needed))
                del self._groups[fid]
                return sdu

        return None

    def _evict_timeouts(self, now_ms: int) -> None:
        to_del = [fid for fid, grp in self._groups.items() if (now_ms - grp.start_ms) >= self._timeout_ms]
        for fid in to_del:
            del self._groups[fid]
