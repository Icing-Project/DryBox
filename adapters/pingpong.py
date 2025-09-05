# adapters/pingpong.py
# MIT License
# Adapter ByteLink de test avec authentification Ed25519 optionnelle:
# - Handshake ping-pong (SYN / SYN-ACK / ACK) avec signatures Ed25519 si cfg["crypto"] présent  L (initiateur) ↔ R (répondeur)
# - Après handshake: émission périodique de DATA (petits pings + "bulk" 400 B pour tester la SAR)
# - Émet des events (hs_syn, hs_synack, hs_done, hs_fail, data_sched, data_rx, crypto_info) -> events.jsonl
from __future__ import annotations

from typing import Dict, List, Optional

# Backend crypto (Ed25519): cryptography (prioritaire) puis pynacl en secours.
_ED_BACKEND = None
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    _ED_BACKEND = "cryptography"
except Exception:  # pragma: no cover
    try:
        from nacl.signing import SigningKey, VerifyKey  # type: ignore
        _ED_BACKEND = "pynacl"
    except Exception:
        _ED_BACKEND = None


def _ed_sign(priv32: bytes, msg: bytes) -> bytes:
    if _ED_BACKEND == "cryptography":
        sk = Ed25519PrivateKey.from_private_bytes(priv32)
        return sk.sign(msg)
    if _ED_BACKEND == "pynacl":  # pragma: no cover
        sk = SigningKey(priv32)
        return bytes(sk.sign(msg).signature)
    raise RuntimeError("No Ed25519 backend available.")


def _ed_verify(pub32: bytes, sig: bytes, msg: bytes) -> bool:
    if _ED_BACKEND == "cryptography":
        try:
            Ed25519PublicKey.from_public_bytes(pub32).verify(sig, msg)
            return True
        except Exception:
            return False
    if _ED_BACKEND == "pynacl":  # pragma: no cover
        try:
            VerifyKey(pub32).verify(msg, sig)
            return True
        except Exception:
            return False
    return False


class Adapter:
    # Types de trames (1 octet)
    _SYN    = 0x01
    _SYNACK = 0x02
    _ACK    = 0x03
    _DATA   = 0x10

    # Domaine de signature (évite les collisions avec des payloads DATA)
    _DOM = b"PPv1|"

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

        # Crypto
        self._crypto_enabled = False
        self._priv: Optional[bytes] = None
        self._pub: Optional[bytes] = None
        self._peer_pub: Optional[bytes] = None
        self._key_id: str = ""
        self._peer_key_id: str = ""

        # Nonces de handshake
        self._nonce_l: Optional[bytes] = None
        self._nonce_r: Optional[bytes] = None

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
        c = (cfg or {}).get("crypto", {})
        # Crypto activable si priv/pub/peer_pub sont présents et si un backend est dispo
        if _ED_BACKEND is not None and all(k in c for k in ("priv", "pub", "peer_pub")):
            self._priv = bytes(c["priv"])
            self._pub = bytes(c["pub"])
            self._peer_pub = bytes(c["peer_pub"])
            self._key_id = str(c.get("key_id", "")) or ""
            self._peer_key_id = str(c.get("peer_key_id", "")) or ""
            self._crypto_enabled = True
        else:
            self._crypto_enabled = False  # fallback silencieux (rétro-compat)

    def start(self, ctx) -> None:
        self.ctx = ctx
        self._role = "init" if ctx.side == "L" else "resp"
        self._state = "IDLE"
        self._seq = 0
        now = self.ctx.now_ms()
        self._last_data_ms = now

        # Event d’info crypto (non sensible)
        if self._crypto_enabled:
            self.ctx.emit_event(
                "crypto_info",
                {
                    "key_id": self._key_id,
                    "peer_key_id": self._peer_key_id,
                    "pub_hex": self._pub.hex(),
                    "peer_pub_hex": self._peer_pub.hex(),
                },
            )

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
                ok = True
                if self._crypto_enabled:
                    # payload: L_nonce(8) || sig_L(64)
                    if len(payload) < 8 + 64:
                        return
                    self._nonce_l = payload[:8]
                    sig_l = payload[8:8+64]
                    msg = self._DOM + b"SYN|" + self._nonce_l
                    ok = _ed_verify(self._peer_pub, sig_l, msg)  # type: ignore[arg-type]
                if ok:
                    # Répondre par SYN-ACK: payload = R_nonce(8) || sig_R(64) sur ("SYNACK|" + L_nonce + R_nonce)
                    self._enqueue(self._mk(self._SYNACK, self._mk_synack_payload()))
                    self._state = "SYNACK_SENT"
                    self.ctx.emit_event("hs_synack", {"peer_seq": seq, "auth": "ok" if self._crypto_enabled else "none"})
                else:
                    self.ctx.emit_event("hs_fail", {"reason": "bad_sig_syn"})
        elif typ == self._SYNACK:
            if self._role == "init" and self._state in ("SYN_SENT", "SYN_RETRY", "IDLE"):
                ok = True
                if self._crypto_enabled:
                    # payload: R_nonce(8) || sig_R(64) sur ("SYNACK|" + L_nonce + R_nonce)
                    if len(payload) < 8 + 64 or self._nonce_l is None:
                        return
                    self._nonce_r = payload[:8]
                    sig_r = payload[8:8+64]
                    msg = self._DOM + b"SYNACK|" + self._nonce_l + self._nonce_r
                    ok = _ed_verify(self._peer_pub, sig_r, msg)  # type: ignore[arg-type]
                if ok:
                    # Finaliser par ACK (signé si crypto)
                    self._enqueue(self._mk(self._ACK, self._mk_ack_payload()))
                    self._handshake_done(now, who="initiator", auth="ok" if self._crypto_enabled else "none")
                else:
                    self.ctx.emit_event("hs_fail", {"reason": "bad_sig_synack"})
        elif typ == self._ACK:
            if self._role == "resp" and not self._hs_done:
                ok = True
                if self._crypto_enabled:
                    # payload: sig_L2(64) sur ("ACK|" + L_nonce + R_nonce)
                    if len(payload) < 64 or self._nonce_l is None or self._nonce_r is None:
                        return
                    sig_l2 = payload[:64]
                    msg = self._DOM + b"ACK|" + self._nonce_l + self._nonce_r
                    ok = _ed_verify(self._peer_pub, sig_l2, msg)  # type: ignore[arg-type]
                if ok:
                    self._handshake_done(now, who="responder", auth="ok" if self._crypto_enabled else "none")
                else:
                    self.ctx.emit_event("hs_fail", {"reason": "bad_sig_ack"})
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
                    self._enqueue(self._mk(self._SYN, self._mk_syn_payload(retry=True)))
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

    def _mk_syn_payload(self, retry: bool = False) -> bytes:
        if not self._crypto_enabled:
            # Ancien comportement: petite charge utile textuelle
            return b"hello" if not retry else b"retry"
        # Génère L_nonce une fois
        if self._nonce_l is None:
            # 8 octets pseudo-aléatoires déterministes via RNG DryBox côté adapter
            r = self.ctx.rng.getrandbits(64)
            self._nonce_l = int(r).to_bytes(8, "little")
        msg = self._DOM + b"SYN|" + self._nonce_l
        sig = _ed_sign(self._priv, msg)  # type: ignore[arg-type]
        return self._nonce_l + sig

    def _mk_synack_payload(self) -> bytes:
        if not self._crypto_enabled:
            return b"ok"
        # Génère R_nonce
        r = self.ctx.rng.getrandbits(64)
        self._nonce_r = int(r).to_bytes(8, "little")
        msg = self._DOM + b"SYNACK|" + (self._nonce_l or b"\x00"*8) + self._nonce_r
        sig = _ed_sign(self._priv, msg)  # type: ignore[arg-type]
        return self._nonce_r + sig

    def _mk_ack_payload(self) -> bytes:
        if not self._crypto_enabled:
            return b""
        msg = self._DOM + b"ACK|" + (self._nonce_l or b"\x00"*8) + (self._nonce_r or b"\x00"*8)
        sig = _ed_sign(self._priv, msg)  # type: ignore[arg-type]
        return sig

    def _send_syn(self, now_ms: int) -> None:
        self._enqueue(self._mk(self._SYN, self._mk_syn_payload()))
        self._hs_start_ms = now_ms
        self._last_syn_ms = now_ms
        self._syn_retry = 0
        self._state = "SYN_SENT"
        self.ctx.emit_event("hs_syn", {"role": self._role})

    def _handshake_done(self, now_ms: int, who: str, auth: str) -> None:
        self._hs_done = True
        start = self._hs_start_ms if self._hs_start_ms is not None else now_ms
        dt = int(now_ms - start)
        self.ctx.emit_event("hs_done", {"role": self._role, "who": who, "time_ms": dt, "auth": auth})
