# adapters/pingpong.py
# MIT License
# Adapter ByteLink de test:
# - Handshake ping-pong (SYN / SYN-ACK / ACK) L (initiateur) ↔ R (répondeur)
# - Après handshake: émission périodique de DATA (petits pings + "bulk" 400 B pour tester la SAR)
# - Émet des events (hs_syn, hs_synack, hs_done, data_sched, data_rx) -> events.jsonl
from __future__ import annotations

from typing import Dict, List, Optional

class Adapter:
    # Types de trames (1 octet)
    _SYN    = 0x01
    _SYNACK = 0x02
    _ACK    = 0x03
    _DATA   = 0x10

    def __init__(self):
        self.cfg: Dict = {}
        self.ctx = None
        self._role = "init"   # "init" (L) ou "resp" (R)
        self._state = "IDLE"
        self._seq = 0
        self._txq: List[bytes] = []

        # Handshake
        self._hs_start_ms: Optional[int] = None
        self._hs_done = False
        self._last_syn_ms = -10**9
        self._syn_retry = 0

        # DATA périodique
        self._last_data_ms = -10**9
        self._data_period_ms = 200

    # ---- ABI discovery ----
    def nade_capabilities(self) -> Dict:
        # Mode A uniquement pour ce smoke test
        return {
            "abi_version": "1.0",
            "bytelink": True,
            "audioblock": False,
            "sdu_max_bytes": 1024,
        }

    # ---- Cycle de vie ----
    def init(self, cfg: Dict) -> None:
        self.cfg = cfg

    def start(self, ctx) -> None:
        self.ctx = ctx
        self._role = "init" if ctx.side == "L" else "resp"
        self._state = "IDLE"
        self._seq = 0
        now = self.ctx.now_ms()
        self._last_data_ms = now

        if self._role == "init":
            # L démarre la négociation
            self._send_syn(now)

    def stop(self) -> None:
        pass

    # ---- API ByteLink ----
    def on_link_rx(self, data: bytes) -> None:
        if not data or len(data) < 5:
            return
        typ = data[0]
        seq = int.from_bytes(data[1:5], "little")
        payload = data[5:]
        now = self.ctx.now_ms()

        if typ == self._SYN:
            if not self._hs_done and self._role == "resp":
                if self._hs_start_ms is None:
                    self._hs_start_ms = now
                # Répondre par SYN-ACK
                self._enqueue(self._mk(self._SYNACK, b"ok"))
                self._state = "SYNACK_SENT"
                self.ctx.emit_event("hs_synack", {"peer_seq": seq})
        elif typ == self._SYNACK:
            if self._role == "init" and self._state in ("SYN_SENT", "SYN_RETRY", "IDLE"):
                # Finaliser par ACK
                self._enqueue(self._mk(self._ACK, b""))
                self._handshake_done(now, who="initiator")
        elif typ == self._ACK:
            if self._role == "resp" and not self._hs_done:
                self._handshake_done(now, who="responder")
        elif typ == self._DATA:
            # Réception de données
            self.ctx.emit_event("data_rx", {"bytes": len(payload), "seq": seq})

    def poll_link_tx(self, budget: int) -> List[bytes]:
        out = self._txq[:budget]
        del self._txq[:budget]
        return out

    def on_timer(self, t_ms: int) -> None:
        # Retransmission SYN côté initiateur
        if not self._hs_done and self._role == "init" and self._state in ("SYN_SENT", "SYN_RETRY"):
            if (t_ms - self._last_syn_ms) >= 200:
                if self._syn_retry < 5:
                    self._enqueue(self._mk(self._SYN, b"retry"))
                    self._last_syn_ms = t_ms
                    self._syn_retry += 1
                    self._state = "SYN_RETRY"
                    self.ctx.emit_event("hs_syn", {"role": self._role, "retry": self._syn_retry})
                else:
                    self._hs_done = True
                    self.ctx.emit_event("hs_fail", {"reason": "syn_timeout"})

        # Après handshake: trafic périodique
        if self._hs_done and (t_ms - self._last_data_ms) >= self._data_period_ms:
            # Un petit ping la plupart du temps, et un "bulk" de 400 B ~ 1x/s pour tester la SAR (mtu=96)
            bulk = (t_ms // 1000) % 5 == 0
            payload = (b"ping" if not bulk else (b"D" * 400))
            self._enqueue(self._mk(self._DATA, payload))
            self.ctx.emit_event("data_sched", {"bytes": len(payload), "bulk": bool(bulk)})
            self._last_data_ms = t_ms

    # ---- Helpers ----
    def _mk(self, typ: int, payload: bytes) -> bytes:
        seq = self._seq
        self._seq = (self._seq + 1) & 0xFFFFFFFF
        return bytes([typ]) + seq.to_bytes(4, "little") + payload

    def _enqueue(self, sdu: bytes) -> None:
        self._txq.append(sdu)

    def _send_syn(self, now_ms: int) -> None:
        self._enqueue(self._mk(self._SYN, b"hello"))
        self._hs_start_ms = now_ms
        self._last_syn_ms = now_ms
        self._syn_retry = 0
        self._state = "SYN_SENT"
        self.ctx.emit_event("hs_syn", {"role": self._role})

    def _handshake_done(self, now_ms: int, who: str) -> None:
        self._hs_done = True
        start = self._hs_start_ms if self._hs_start_ms is not None else now_ms
        dt = int(now_ms - start)
        self.ctx.emit_event("hs_done", {"role": self._role, "who": who, "time_ms": dt})
