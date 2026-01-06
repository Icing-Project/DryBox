# Test Traffic Adapter for DryBox
# Generates continuous traffic to test network metrics graphs
# This adapter sends periodic packets to exercise the bearer simulation

from __future__ import annotations
from collections import deque
from typing import Any, Deque, List, Optional, Tuple
import random

try:
    import numpy as np
except Exception:
    np = None

ABI_VERSION = "dbx-v1"
SDU_MAX_BYTES = 512


class Adapter:
    """
    Test adapter that generates continuous traffic for graph testing.
    - Byte mode: sends periodic packets at configurable rate
    - Audio mode: generates test tones / silence patterns
    """

    def __init__(self):
        self.cfg: dict = {}
        self.ctx: Optional[Any] = None
        self.mode: str = "byte"
        self.side: str = "L"
        self._t_ms: int = 0
        self._txq: Deque[Tuple[bytes, int]] = deque()
        self._rng = random.Random(42)

        # Traffic generation params
        self._packet_interval_ms: int = 20  # Send packet every 20ms
        self._last_tx_ms: int = 0
        self._packet_size: int = 100  # bytes per packet
        self._seq: int = 0

        # Stats
        self._tx_count: int = 0
        self._rx_count: int = 0

    def nade_capabilities(self) -> dict:
        return {
            "abi_version": ABI_VERSION,
            "bytelink": True,
            "audioblock": True,
            "sdu_max_bytes": SDU_MAX_BYTES,
            "audioparams": {"sr": 8000, "block": 160},
        }

    def init(self, cfg: dict) -> None:
        self.cfg = cfg or {}
        self.side = self.cfg.get("side", "L")
        self.mode = self.cfg.get("mode", "byte")

        # Get traffic params from config if available
        traffic_cfg = self.cfg.get("traffic", {})
        self._packet_interval_ms = traffic_cfg.get("interval_ms", 20)
        self._packet_size = traffic_cfg.get("packet_size", 100)

    def start(self, ctx: Any) -> None:
        self.ctx = ctx
        self._t_ms = 0
        self._last_tx_ms = 0
        self._seq = 0
        self._tx_count = 0
        self._rx_count = 0
        self._txq.clear()

        if self.ctx:
            self.ctx.emit_event("log", {
                "level": "info",
                "msg": f"[TestTraffic:{self.side}] Started in {self.mode} mode, "
                       f"interval={self._packet_interval_ms}ms, size={self._packet_size}B"
            })

    def stop(self) -> None:
        if self.ctx:
            self.ctx.emit_event("log", {
                "level": "info",
                "msg": f"[TestTraffic:{self.side}] Stopped. TX={self._tx_count} RX={self._rx_count}"
            })

    def on_timer(self, t_ms: int) -> None:
        self._t_ms = t_ms

        if self.mode == "byte":
            # Generate periodic traffic
            if t_ms - self._last_tx_ms >= self._packet_interval_ms:
                self._generate_packet()
                self._last_tx_ms = t_ms

    def _generate_packet(self) -> None:
        """Generate a test packet with sequence number and padding."""
        # Header: 4 bytes sequence number + side marker
        header = self._seq.to_bytes(4, 'big') + self.side.encode('ascii')

        # Payload: random bytes to fill packet size
        payload_size = max(0, self._packet_size - len(header))
        payload = bytes(self._rng.randint(0, 255) for _ in range(payload_size))

        packet = header + payload
        self._txq.append((packet, self._t_ms))
        self._seq += 1
        self._tx_count += 1

    def poll_link_tx(self, budget: int) -> List[Tuple[bytes, int]]:
        if self.mode != "byte":
            return []
        out: List[Tuple[bytes, int]] = []
        while self._txq and len(out) < budget:
            out.append(self._txq.popleft())
        return out

    def on_link_rx(self, sdu: bytes) -> None:
        if self.mode != "byte" or not sdu:
            return
        self._rx_count += 1

        # Parse received packet
        if len(sdu) >= 5:
            seq = int.from_bytes(sdu[:4], 'big')
            sender = sdu[4:5].decode('ascii', errors='replace')
            # Could log or track out-of-order packets here

    # ---- AudioBlock I/O ----
    def pull_tx_block(self, t_ms: int):
        """Generate audio test signal."""
        if np is None:
            return None

        # Generate a simple sine wave test tone at 440Hz
        sr = 8000
        block_size = 160
        freq = 440 if self.side == "L" else 880  # Different freq per side

        t = np.arange(block_size) / sr + (t_ms / 1000.0)
        samples = np.sin(2 * np.pi * freq * t) * 8000  # amplitude
        return samples.astype(np.int16)

    def push_rx_block(self, pcm, t_ms: int) -> None:
        """Receive audio block - just count for stats."""
        self._rx_count += 1
