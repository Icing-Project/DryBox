# MIT License
# drybox/core/metrics.py — Writer CSV + events.jsonl (extrait du runner v1)
from __future__ import annotations

import csv
import json
import pathlib
from typing import Any, Dict, Optional

# En-tête strictement identique (ordre inclus) à celui utilisé dans runner.py
CSV_HEADER = [
    "t_ms",
    "side",
    "layer",
    "event",
    "rtt_ms_est",
    "latency_ms",
    "jitter_ms",
    "loss_rate",
    "reorder_rate",
    "goodput_bps",
    "snr_db_est",
    "ber",
    "per",
    "cfo_hz_est",
    "lock_ratio",
    "hs_time_ms",
    "rekey_ms",
    "aead_fail_cnt",
]


def _fmt(x: Optional[float]) -> str:
    if x is None:
        return ""
    return f"{x:.6f}"


class MetricsWriter:
    """
    Écrit:
      - metrics.csv (colonnes fixes CSV_HEADER)
      - events.jsonl (lignes JSON {"t_ms","side","type","payload"})
    """

    def __init__(self, csv_path: pathlib.Path, events_path: pathlib.Path):
        self._csv_fp = open(csv_path, "w", newline="")
        self._csv = csv.DictWriter(self._csv_fp, fieldnames=CSV_HEADER)
        self._csv.writeheader()
        self._events_fp = open(events_path, "w", encoding="utf-8")

    def write_metric(
        self,
        *,
        t_ms: int,
        side: str,
        layer: str,
        event: str,
        rtt_ms_est: Optional[float] = None,
        latency_ms: Optional[float] = None,
        jitter_ms: Optional[float] = None,
        loss_rate: Optional[float] = None,
        reorder_rate: Optional[float] = None,
        goodput_bps: Optional[float] = None,
        snr_db_est: Optional[float] = None,
        ber: Optional[float] = None,
        per: Optional[float] = None,
        cfo_hz_est: Optional[float] = None,
        lock_ratio: Optional[float] = None,
        hs_time_ms: Optional[float] = None,
        rekey_ms: Optional[float] = None,
        aead_fail_cnt: Optional[int] = None,
    ) -> None:
        row = {
            "t_ms": t_ms,
            "side": side,
            "layer": layer,
            "event": event,
            "rtt_ms_est": _fmt(rtt_ms_est),
            "latency_ms": _fmt(latency_ms),
            "jitter_ms": _fmt(jitter_ms),
            "loss_rate": _fmt(loss_rate),
            "reorder_rate": _fmt(reorder_rate),
            "goodput_bps": _fmt(goodput_bps),
            "snr_db_est": _fmt(snr_db_est),
            "ber": _fmt(ber),
            "per": _fmt(per),
            "cfo_hz_est": _fmt(cfo_hz_est),
            "lock_ratio": _fmt(lock_ratio),
            "hs_time_ms": _fmt(hs_time_ms),
            "rekey_ms": _fmt(rekey_ms),
            "aead_fail_cnt": aead_fail_cnt if aead_fail_cnt is not None else "",
        }
        self._csv.writerow(row)

    def write_event(self, t_ms: int, side: str, typ: str, payload: Dict[str, Any]) -> None:
        rec = {"t_ms": t_ms, "side": side, "type": typ, "payload": payload}
        
        # Print all "msg" type events
        if typ == "log" and isinstance(payload, dict) and payload.get("level") == "msg":
            print(f"[{side}@{t_ms}ms] {payload.get('msg')}", flush=True)
        
        # Extract and callback for demod metrics with total_bytes_processed
        if typ == "metric" and isinstance(payload, dict):
            event = payload.get("event")
            if event == "demod":
                total_bytes = payload.get("total_bytes_processed")
                if total_bytes is not None and hasattr(self, '_bytes_callback'):
                    try:
                        self._bytes_callback(side, total_bytes)
                    except Exception as e:
                        pass
        
        self._events_fp.write(json.dumps(rec) + "\n")

    def set_bytes_callback(self, callback):
        """Register callback for total_bytes_processed updates.
        Callback signature: callback(side: str, total_bytes: int)
        """
        self._bytes_callback = callback

    def close(self) -> None:
        try:
            self._csv_fp.flush()
            self._csv_fp.close()
        finally:
            self._events_fp.flush()
            self._events_fp.close()
