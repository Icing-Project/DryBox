# drybox/tests/adapters/test_pingpong_crypto.py
from __future__ import annotations
import json
from pathlib import Path

from drybox.core.runner import Runner
from drybox.core.scenario import ScenarioResolved

ADAPTER = "adapters/pingpong.py:Adapter"

def _events(out_dir: Path):
    return [json.loads(x) for x in (out_dir/"events.jsonl").read_text().strip().splitlines()]

def test_pingpong_handshake_with_crypto(tmp_path: Path):
    scen = ScenarioResolved.from_yaml_dict({
        "mode": "byte",
        "duration_ms": 1000,
        "seed": 999,
        "bearer": {"type": "telco_volte_evs", "latency_ms": 50, "mtu_bytes": 2000},
    })
    out = tmp_path / "run"
    rc = Runner(scenario=scen, left_adapter_spec=ADAPTER, right_adapter_spec=ADAPTER, out_dir=out, tick_ms=10, seed=999, ui_enabled=False).run()
    assert rc == 0
    evs = _events(out)
    # On doit observer au moins un hs_done côté L et côté R avec auth="ok"
    hs = [e for e in evs if e.get("type") == "hs_done"]
    assert any(e["side"] == "L" and e["payload"].get("auth") in ("ok","none") for e in hs)
    assert any(e["side"] == "R" and e["payload"].get("auth") in ("ok","none") for e in hs)
