# drybox/core/crypto_keys.py
# MIT License
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
from typing import Any, Dict, Optional, Tuple

# --- Ed25519 backend (cryptography ou pynacl) ---
_ED25519_BACKEND = None
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    _ED25519_BACKEND = "cryptography"
except Exception:  # pragma: no cover
    try:
        from nacl.signing import SigningKey  # type: ignore
        _ED25519_BACKEND = "pynacl"
    except Exception:
        _ED25519_BACKEND = None


def _hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Extract + Expand (RFC5869), SHA-256."""
    if not salt:
        salt = b"\x00" * hashlib.sha256().digest_size
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        okm += t
        counter += 1
    return okm[:length]


def _parse_priv_any(v: Any) -> Optional[bytes]:
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        b = bytes(v)
    elif isinstance(v, str):
        s = v.strip()
        # Heuristique: hex pur → hex ; sinon on tente base64
        try:
            if all(c in "0123456789abcdefABCDEF" for c in s) and len(s) % 2 == 0:
                b = bytes.fromhex(s)
            else:
                b = base64.b64decode(s, validate=False)
        except (binascii.Error, ValueError):
            raise SystemExit(4)
    elif isinstance(v, dict):
        if "hex" in v:
            try:
                b = bytes.fromhex(v["hex"].strip())
            except Exception:
                raise SystemExit(4)
        elif "b64" in v:
            try:
                b = base64.b64decode(v["b64"], validate=False)
            except Exception:
                raise SystemExit(4)
        elif "path" in v:
            try:
                with open(v["path"], "rb") as fp:
                    data = fp.read().strip()
                # retry parse as str
                return _parse_priv_any(data.decode("ascii", errors="ignore"))
            except Exception:
                raise SystemExit(4)
        else:
            raise SystemExit(4)
    else:
        raise SystemExit(4)

    # Normalise à seed 32 octets (Ed25519)
    if len(b) == 32:
        return b
    if len(b) == 64:
        # Tolérer 64 (clé étendue) → on garde les 32 premiers octets (seed)
        return b[:32]
    raise SystemExit(4)


def _pub_from_priv_seed(priv32: bytes) -> bytes:
    if _ED25519_BACKEND == "cryptography":
        sk = Ed25519PrivateKey.from_private_bytes(priv32)
        pk = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return pk
    if _ED25519_BACKEND == "pynacl":  # pragma: no cover
        sk = SigningKey(priv32)
        return bytes(sk.verify_key)
    raise RuntimeError(
        "No Ed25519 backend available. Install 'cryptography' (recommended) or 'pynacl'."
    )


def derive_priv_seed(*, seed: int, left_spec: str, right_spec: str, side: str) -> bytes:
    """
    Dérive une seed Ed25519 (32B) déterministe à partir du seed scénario et des specs d'adapters.
    - Stable pour un given (seed, left_spec, right_spec, side)
    - Indépendant des paramètres de sweep (ex: snr_db)
    """
    ikm = int(seed).to_bytes(8, "little", signed=False)
    a = left_spec.encode("utf-8")
    b = right_spec.encode("utf-8")
    aa, bb = (a, b) if a <= b else (b, a)
    salt = hashlib.sha256(b"DryBox.Ed25519.v1|" + aa + b"|" + bb).digest()
    info = f"side:{side}".encode("utf-8")
    return _hkdf_sha256(ikm, salt, info, 32)


def resolve_keypairs(
    *,
    scenario_crypto: Optional[Dict[str, Any]],
    seed: int,
    left_spec: str,
    right_spec: str,
) -> Tuple[Tuple[bytes, bytes, str], Tuple[bytes, bytes, str]]:
    """
    Retourne: ((L_priv, L_pub, prov), (R_priv, R_pub, prov))
    prov ∈ {"scenario", "derived"} si la privée vient du scénario ou de la dérivation.
    """
    left_in = None
    right_in = None
    if scenario_crypto:
        left_in = _parse_priv_any(scenario_crypto.get("left_priv"))
        right_in = _parse_priv_any(scenario_crypto.get("right_priv"))

    if left_in is None:
        left_in = derive_priv_seed(seed=seed, left_spec=left_spec, right_spec=right_spec, side="L")
        left_prov = "derived"
    else:
        left_prov = "scenario"

    if right_in is None:
        right_in = derive_priv_seed(seed=seed, left_spec=left_spec, right_spec=right_spec, side="R")
        right_prov = "derived"
    else:
        right_prov = "scenario"

    l_pub = _pub_from_priv_seed(left_in)
    r_pub = _pub_from_priv_seed(right_in)
    return (left_in, l_pub, left_prov), (right_in, r_pub, right_prov)


def key_id(pub32: bytes) -> str:
    return hashlib.sha256(pub32).hexdigest()[:8]
