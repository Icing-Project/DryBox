# adapters/audio_test.py
# Simple sine wave generator for testing Mode B

import numpy as np
from typing import Dict, Any
import sys
sys.path.insert(0, '.')
from adapters.audioblock import AudioBlockAdapter


class AudioTestAdapter(AudioBlockAdapter):
    """Test adapter that generates/receives sine waves"""

    def __init__(self):
        super().__init__()
        # Initialize with defaults
        self.freq_hz = 1000.0
        self.phase = 0.0
        self.rx_buffer = []

    def init(self, cfg: Dict[str, Any]):
        """Initialize with configuration"""
        super().init(cfg)
        # Set frequency based on side
        self.freq_hz = 1000.0 if self.side == "L" else 800.0

    def on_timer(self, t_ms: int) -> None:
        """Update phase tracking"""
        pass

    def pull_tx_block(self, t_ms: int) -> np.ndarray:
        """Generate sine wave PCM block"""
        # Time array for this block
        t = (np.arange(self.BLOCK_SAMPLES, dtype=np.float32) + self.phase) / self.SAMPLE_RATE
        self.phase += self.BLOCK_SAMPLES

        # Generate sine wave with 20% amplitude
        x = 0.2 * np.sin(2 * np.pi * self.freq_hz * t)

        # Convert to int16
        pcm = (x * 32767).astype(np.int16, copy=False)
        return pcm

    def push_rx_block(self, pcm: np.ndarray, t_ms: int) -> None:
        """Receive PCM block"""
        self.rx_buffer.append((t_ms, pcm.copy()))

        # Simple energy detection for metrics
        if self.ctx and hasattr(self.ctx, 'emit_event'):
            energy = np.sqrt(np.mean(pcm.astype(np.float32)**2))
            self.ctx.emit_event(
                typ="audio_rx",
                payload={"energy": float(energy), "samples": len(pcm)}
            )
