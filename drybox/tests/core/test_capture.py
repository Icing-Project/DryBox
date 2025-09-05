import struct
from pathlib import Path

from drybox.core.capture import DbxCapWriter


def test_dbxcap_layout(tmp_path: Path):
    p = tmp_path / "capture.dbxcap"
    w = DbxCapWriter(p)
    w.write(t_ms=42, side="L", layer="bearer", event="tx", data=b"\x01\x02\x03")
    w.close()

    blob = p.read_bytes()
    # Magic + version
    assert blob[:4] == b"DBXC"
    assert blob[4] == 1

    # Record: <QBBB><I><payload>
    off = 5
    t_ms, side_b, layer_b, ev_b = struct.unpack_from("<QBBB", blob, off)
    off += 11
    (length,) = struct.unpack_from("<I", blob, off)
    off += 4
    payload = blob[off:off+length]

    assert t_ms == 42
    assert side_b == 0        # "L"
    assert layer_b == 1       # "bearer"
    assert ev_b == 0          # "tx"
    assert length == 3
    assert payload == b"\x01\x02\x03"
