# drybox/tests/core/test_crypto_keys.py
from __future__ import annotations

import json
from pathlib import Path
import textwrap
import yaml

from drybox.core.runner import Runner
from drybox.core.scenario import ScenarioResolved

ADAPTER_CODE = """
class Adapter:
    def nade_capabilities(self):
        return {"bytelink": True, "audioblock": True}

    def init(self, cfg):
        # Enregistre uniquement des infos non sensibles
        self.pub = cfg["crypto"]["pub"]
        self.peer_pub = cfg["crypto"]["peer_pub"]
        self.key_id = cfg["crypto"]["key_id"]
        self.peer_key_id = cfg["crypto"]["peer_key_id"]
        self.ctx = None

    def start(self, ctx):
        self.ctx = ctx
        # Emet un événement avec des fingerprints (pas de secrets)
        ctx.emit_event("crypto_info", {
            "pub_hex": self.pub.hex(),
            "peer_pub_hex": self.peer_pub.hex(),
            "key_id": self.key_id,
            "peer_key_id": self.peer_key_id
        })

    def on_timer(self, t_ms): pass
    def poll_link_tx(self, budget): return []
    def on_link_rx(self, data: bytes): pass
    def stop(self): pass
"""


def _make_adapter(tmp_path: Path, name: str) -> str:
    p = tmp_path / f"{name}.py"
    p.write_text(ADAPTER_CODE, encoding="utf-8")
    return str(p) + ":Adapter"


def _read_event(out_dir: Path):
    ev = out_dir / "events.jsonl"
    lines = [json.loads(x) for x in ev.read_text(encoding="utf-8").strip().splitlines()]
    # retourne le dernier event (crypto_info)
    for rec in lines:
        if rec.get("type") == "crypto_info":
            return rec
    raise AssertionError("crypto_info not found in events.jsonl")


def test_crypto_derived_and_stable_across_sweep(tmp_path: Path):
    left = _make_adapter(tmp_path, "left_adapter")
    right = _make_adapter(tmp_path, "right_adapter")
    scen_doc = {
        "mode": "byte",
        "duration_ms": 20,
        "seed": 12345,
        "bearer": {"type": "telco_volte_evs", "latency_ms": 50, "mtu_bytes": 2000},
        "channel": {"type": "awgn", "snr_db": [0, 9]},  # sweep à 2 runs
    }
    scen = ScenarioResolved.from_yaml_dict(scen_doc)
    # Run 1
    out1 = tmp_path / "run1"
    Runner(scenario=scen, left_adapter_spec=left, right_adapter_spec=right, out_dir=out1, tick_ms=10, seed=12345,
           ui_enabled=False).run()
    e1 = _read_event(out1)
    # Run 2 (autre suffix, mêmes clés attendues)
    scen2 = scen
    out2 = tmp_path / "run2"
    Runner(scenario=scen2, left_adapter_spec=left, right_adapter_spec=right, out_dir=out2, tick_ms=10, seed=12345,
           ui_enabled=False).run()
    e2 = _read_event(out2)
    assert e1["payload"]["pub_hex"] == e2["payload"]["pub_hex"]
    assert e1["payload"]["peer_pub_hex"] == e2["payload"]["peer_pub_hex"]


def test_crypto_from_scenario_keys(tmp_path: Path):
    left = _make_adapter(tmp_path, "left_adapter2")
    right = _make_adapter(tmp_path, "right_adapter2")

    # Clé privée L en hex (32B), R manquante (dérivée)
    left_priv_hex = "11" * 32  # 32 octets 0x11

    scen_doc = {
        "mode": "byte",
        "duration_ms": 20,
        "seed": 777,
        "bearer": {"type": "telco_volte_evs"},
        "crypto": {"left_priv": {"hex": left_priv_hex}},
    }
    scen = ScenarioResolved.from_yaml_dict(scen_doc)
    out = tmp_path / "out"
    Runner(scenario=scen, left_adapter_spec=left, right_adapter_spec=right, out_dir=out, tick_ms=10, seed=777,
           ui_enabled=False).run()
    rec = _read_event(out)["payload"]
    # On a bien une pub en hex 64 chars
    assert len(rec["pub_hex"]) == 64
    assert len(rec["peer_pub_hex"]) == 64
    # Identifiants présents
    assert len(rec["key_id"]) == 8
    assert len(rec["peer_key_id"]) == 8
    # pubs L et R doivent être différentes
    assert rec["pub_hex"] != rec["peer_pub_hex"]


ADAPTER = "adapters/pingpong.py:Adapter"


def test_pubkeys_dump_created(tmp_path: Path):
    scen = ScenarioResolved.from_yaml_dict({
        "mode": "byte",
        "duration_ms": 50,
        "seed": 123,
        "bearer": {"type": "telco_volte_evs", "latency_ms": 30, "mtu_bytes": 2000},
    })
    out = tmp_path / "run"
    r = Runner(scenario=scen, left_adapter_spec=ADAPTER, right_adapter_spec=ADAPTER, out_dir=out, tick_ms=10, seed=123,
               ui_enabled=False)
    r.run()
    dump = out / "pubkeys.txt"
    assert dump.exists()
    txt = dump.read_text()
    assert "L.key_id=" in txt and "R.key_id=" in txt
    assert "L.pub_hex=" in txt and "R.pub_hex=" in txt
    # 64 hex chars for a 32B pubkey
    for line in txt.splitlines():
        if line.startswith("L.pub_hex=") or line.startswith("R.pub_hex="):
            assert len(line.split("=", 1)[1].strip()) == 64
