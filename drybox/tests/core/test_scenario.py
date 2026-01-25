from __future__ import annotations

import pathlib
import yaml
import pytest

from drybox.core.scenario import ScenarioResolved, ScenarioValidationError


def _write_yaml(tmp_path: pathlib.Path, name: str, doc: dict) -> pathlib.Path:
    p = tmp_path / name
    with open(p, "w", encoding="utf-8") as fp:
        yaml.safe_dump(doc, fp, sort_keys=False)
    return p


def test_valid_yaml_defaults_and_resolved_file(tmp_path: pathlib.Path):
    # Minimal, avec quelques champs — le reste par défaut via le résolveur
    doc = {
        "mode": "byte",
        "duration_ms": 1000,
        "seed": 7,
        "bearer": {"type": "telco_volte_evs", "latency_ms": 60, "jitter_ms": 10, "mtu_bytes": 96},
        "channel": {"type": "awgn", "snr_db": 9},
        "vocoder": {"type": "evs13k2_mock", "vad_dtx": True},
        "cfo_hz": 0,
        "ppm": 0,
    }
    p = _write_yaml(tmp_path, "ok.yaml", doc)
    scen = ScenarioResolved.from_yaml(p)
    assert scen.mode == "byte"
    assert scen.duration_ms == 1000
    assert scen.bearer.type == "telco_volte_evs"
    assert scen.channel["snr_db"] == 9

    out = tmp_path / "scenario.resolved.yaml"
    scen.write_resolved_yaml(out)
    assert out.exists()
    txt = out.read_text(encoding="utf-8")
    assert "mode: byte" in txt
    assert "latency_ms: 60" in txt


def test_invalid_yaml_raises(tmp_path: pathlib.Path):
    # snr_db doit être number|array[number] ; une string doit invalider
    doc = {
        "duration_ms": 2500,
        "bearer": {"type": "telco_volte_evs"},
        "channel": {"type": "awgn", "snr_db": "bad"},
        "vocoder": {"type": "amr12k2_mock"},
    }
    p = _write_yaml(tmp_path, "ko.yaml", doc)
    with pytest.raises(ScenarioValidationError):
        _ = ScenarioResolved.from_yaml(p)


def test_sweep_snr_values(tmp_path: pathlib.Path):
    doc = {
        "duration_ms": 1000,
        "bearer": {"type": "telco_volte_evs"},
        "channel": {"type": "awgn", "snr_db": [0, 3]},
        "vocoder": {"type": "evs13k2_mock"},
    }
    p = _write_yaml(tmp_path, "sweep.yaml", doc)
    base = ScenarioResolved.from_yaml(p)
    clones = base.expand_sweep()
    assert len(clones) == 2
    suffixes = sorted(s for s, _ in clones)
    assert suffixes == ["snr_0", "snr_3"]
    # Valeurs scalaires dans les clones
    vals = sorted(c.channel["snr_db"] for _, c in clones)
    assert vals == [0, 3]
