import csv
import json
from pathlib import Path

from drybox.core.metrics import MetricsWriter, CSV_HEADER


def test_metrics_header_and_rows(tmp_path: Path):
    csv_p = tmp_path / "metrics.csv"
    ev_p = tmp_path / "events.jsonl"
    mw = MetricsWriter(csv_p, ev_p)

    # Une ligne de métriques avec quelques champs
    mw.write_metric(
        t_ms=1234,
        side="L",
        layer="bearer",
        event="tx",
        rtt_ms_est=120.0,
        latency_ms=60.0,
        jitter_ms=5.5,
        loss_rate=0.01,
        reorder_rate=0.0,
        goodput_bps=8000.0,
        aead_fail_cnt=0,
    )
    # Un event libre
    mw.write_event(1234, "L", "hs_syn", {"role": "init"})
    mw.close()

    # Header identique et dans le même ordre
    with open(csv_p, newline="") as fp:
        r = csv.reader(fp)
        header = next(r)
        assert header == CSV_HEADER
        row = next(r)
        assert row[0] == "1234"  # t_ms
        assert row[3] == "tx"    # event
        assert row[4] == "120.000000"  # rtt_ms_est formaté

    # events.jsonl écrit une ligne JSON bien formée
    lines = ev_p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["type"] == "hs_syn"
    assert rec["payload"]["role"] == "init"
