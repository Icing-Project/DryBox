# nade_adapter.py - DryBox adapter wrapping Nade-Python
#
# This adapter provides access to the full Nade protocol implementation
# from the Nade-Python package, following the DryBox v1 adapter interface.
#
# Usage in scenario YAML:
#   left:
#     adapter: nade_adapter.py
#
# Or from command line:
#   --left adapters/nade_adapter.py:Adapter

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Add Nade-Python to path if not already installed
NADE_PYTHON_PATH = Path(__file__).resolve().parents[2] / "Nade-Python"
if NADE_PYTHON_PATH.exists() and str(NADE_PYTHON_PATH) not in sys.path:
    sys.path.insert(0, str(NADE_PYTHON_PATH))

try:
    import numpy as np
except ImportError:
    np = None

# Try to import from Nade-Python's adapter
try:
    from adapter.drybox_adapter import Adapter as NadeAdapter
    NADE_AVAILABLE = True
except ImportError:
    NADE_AVAILABLE = False
    NadeAdapter = None

# Try to import AudioStack for audio mode
try:
    from nade.audio import AudioStack
    AUDIO_STACK_AVAILABLE = True
except ImportError:
    AUDIO_STACK_AVAILABLE = False
    AudioStack = None


ABI_VERSION = "dbx-v1"
SDU_MAX_BYTES = 1024


class Adapter:
    """
    DryBox v1 adapter for Nade-Python.

    Wraps the Nade protocol implementation for use in DryBox simulations.
    Supports both ByteLink (protocol testing) and AudioBlock (voice transport) modes.
    """

    def __init__(self):
        self.cfg: dict = {}
        self.ctx: Optional[Any] = None
        self.mode: str = "audio"
        self.side: str = "L"
        self._inner: Optional[Any] = None  # Inner Nade adapter if available
        self._audio_stack: Optional[Any] = None
        self._fallback_mode: bool = False

    def nade_capabilities(self) -> dict:
        """Declare adapter capabilities."""
        return {
            "abi_version": ABI_VERSION,
            "bytelink": True,
            "audioblock": True,
            "sdu_max_bytes": SDU_MAX_BYTES,
            "audioparams": {"sr": 8000, "block": 160},
        }

    def init(self, cfg: dict) -> None:
        """Initialize with configuration from DryBox runner."""
        self.cfg = cfg or {}
        self.side = self.cfg.get("side", "L")
        self.mode = self.cfg.get("mode", "audio")

        # Try to use the full Nade adapter
        if NADE_AVAILABLE and NadeAdapter is not None:
            try:
                self._inner = NadeAdapter()
                self._inner.init(cfg)
                self._fallback_mode = False
                return
            except Exception as e:
                print(f"[NadeAdapter] Failed to init inner adapter: {e}")

        # Fallback to simple mode
        self._fallback_mode = True
        print(f"[NadeAdapter:{self.side}] Running in fallback mode (Nade-Python not available)")

    def start(self, ctx: Any) -> None:
        """Start the adapter with DryBox context."""
        self.ctx = ctx

        if not self._fallback_mode and self._inner is not None:
            try:
                self._inner.start(ctx)
                return
            except Exception as e:
                print(f"[NadeAdapter] Failed to start inner adapter: {e}")
                self._fallback_mode = True

        # Fallback: setup basic audio stack if available
        if self.mode == "audio" and AUDIO_STACK_AVAILABLE and AudioStack is not None:
            try:
                modem_cfg = self.cfg.get("modem", {}) or {}
                self._audio_stack = AudioStack(
                    modem=modem_cfg.get("modem", "bfsk"),
                    modem_cfg=modem_cfg.get("modem_cfg", {}),
                    logger=self._log
                )
                # Queue a test message
                test_msg = f"Hello from {self.side} side!"
                self._audio_stack.queue_text(test_msg)
                ctx.emit_event("text_tx", {"text": test_msg})
            except Exception as e:
                print(f"[NadeAdapter] Failed to init AudioStack: {e}")
                self._audio_stack = None

    def stop(self) -> None:
        """Stop the adapter."""
        if self._inner is not None and hasattr(self._inner, 'stop'):
            self._inner.stop()

    def on_timer(self, t_ms: int) -> None:
        """Timer callback."""
        if not self._fallback_mode and self._inner is not None:
            if hasattr(self._inner, 'on_timer'):
                self._inner.on_timer(t_ms)

    # ---- ByteLink Mode ----

    def poll_link_tx(self, budget: int):
        """Poll for data to transmit (ByteLink mode)."""
        if not self._fallback_mode and self._inner is not None:
            if hasattr(self._inner, 'poll_link_tx'):
                return self._inner.poll_link_tx(budget)
        return []

    def on_link_rx(self, sdu: bytes) -> None:
        """Receive data (ByteLink mode)."""
        if not self._fallback_mode and self._inner is not None:
            if hasattr(self._inner, 'on_link_rx'):
                self._inner.on_link_rx(sdu)

    # ---- AudioBlock Mode ----

    def push_tx_block(self, t_ms: int):
        """Generate audio block to transmit."""
        # Try inner adapter first
        if not self._fallback_mode and self._inner is not None:
            # Check for pull_tx_block (Nade-Python uses this name)
            if hasattr(self._inner, 'pull_tx_block'):
                return self._inner.pull_tx_block(t_ms)
            if hasattr(self._inner, 'push_tx_block'):
                return self._inner.push_tx_block(t_ms)

        # Fallback to AudioStack
        if self._audio_stack is not None:
            try:
                return self._audio_stack.pull_tx_block(t_ms)
            except Exception:
                pass

        # Return silence
        if np is not None:
            return np.zeros(160, dtype=np.int16)
        return None

    def pull_rx_block(self, pcm, t_ms: int) -> None:
        """Receive processed audio block."""
        # Try inner adapter first
        if not self._fallback_mode and self._inner is not None:
            # Check for push_rx_block (Nade-Python uses this name)
            if hasattr(self._inner, 'push_rx_block'):
                self._inner.push_rx_block(pcm, t_ms)
                return
            if hasattr(self._inner, 'pull_rx_block'):
                self._inner.pull_rx_block(pcm, t_ms)
                return

        # Fallback to AudioStack
        if self._audio_stack is not None:
            try:
                self._audio_stack.push_rx_block(pcm, t_ms)
                # Check for received text
                texts = self._audio_stack.pop_received_texts()
                for txt in texts:
                    if self.ctx:
                        self.ctx.emit_event("text_rx", {"text": txt})
                        self.ctx.emit_event("log", {"level": "info", "msg": f"RX: {txt}"})
            except Exception:
                pass

    def _log(self, level: str, payload: Any) -> None:
        """Logger callback for AudioStack."""
        if self.ctx is None:
            return
        if level == "metric" and isinstance(payload, dict):
            self.ctx.emit_event("metric", payload)
        elif isinstance(payload, str):
            self.ctx.emit_event("log", {"level": "info", "msg": payload})
        else:
            self.ctx.emit_event("log", {"level": str(level), "msg": str(payload)})
