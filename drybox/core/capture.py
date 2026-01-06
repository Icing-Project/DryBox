# MIT License
# drybox/core/capture.py — Writer binaire TLV rejouable (.dbxcap) (extrait du runner v1)
from __future__ import annotations

import pathlib
import struct

# On fige ici les libellés pour éviter une dépendance circulaire avec runner.py
EVENT_TX = "tx"
EVENT_RX = "rx"
EVENT_DROP = "drop"
LAYER_BYTELINK = "bytelink"
LAYER_BEARER = "bearer"


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
