"""Audio File Adapter - Load and play audio files through DryBox simulation.

This adapter allows testing with real audio files (WAV format) instead of
synthetic test tones. The audio is played back in 20ms blocks (160 samples at 8kHz)
through the simulation pipeline.

Usage in scenario YAML:
    left:
      adapter: adapters/audio_file_adapter.py:AudioFileAdapter
      modem:
        audio_file: /path/to/audio.wav
        loop: true  # optional, default true

Requirements:
    - Audio file must be 8000 Hz sample rate (narrowband)
    - Mono channel
    - WAV format (other formats require scipy or soundfile)
"""

from __future__ import annotations

import wave
import struct
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


class AudioFileAdapter:
    """Adapter that plays audio from a WAV file."""

    SAMPLE_RATE = 8000
    BLOCK_SIZE = 160  # 20ms at 8kHz

    def nade_capabilities(self) -> Dict[str, Any]:
        """Declare adapter capabilities."""
        return {
            "bytelink": False,
            "audioblock": True,
            "version": "1.0",
        }

    def init(self, cfg: Dict[str, Any]) -> None:
        """Initialize adapter with configuration."""
        self.cfg = cfg
        self.side = cfg.get("side", "L")
        self.audio_data: Optional[np.ndarray] = None
        self.position = 0
        self.loop = True
        self.ctx = None

        # Audio file path can be in modem config or directly in cfg
        modem_cfg = cfg.get("modem", {}) or {}
        self.audio_file = modem_cfg.get("audio_file") or cfg.get("audio_file")
        self.loop = modem_cfg.get("loop", True)

        # Received audio storage (for potential analysis)
        self.rx_blocks = []
        self.rx_count = 0

    def start(self, ctx) -> None:
        """Start the adapter - load audio file."""
        self.ctx = ctx

        if self.audio_file:
            self._load_audio_file(self.audio_file)
            if self.audio_data is not None:
                duration_ms = len(self.audio_data) / self.SAMPLE_RATE * 1000
                ctx.emit_event("audio_file_loaded", {
                    "file": str(self.audio_file),
                    "samples": len(self.audio_data),
                    "duration_ms": duration_ms,
                    "loop": self.loop,
                })
        else:
            # No file specified - generate silence
            ctx.emit_event("audio_file_warning", {
                "message": "No audio_file specified, generating silence",
            })
            self.audio_data = np.zeros(self.BLOCK_SIZE * 50, dtype=np.int16)

    def _load_audio_file(self, filepath: str) -> None:
        """Load audio from WAV file."""
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {filepath}")

        if path.suffix.lower() != ".wav":
            raise ValueError(f"Only WAV files supported, got: {path.suffix}")

        try:
            with wave.open(str(path), 'rb') as wav:
                # Validate format
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                framerate = wav.getframerate()
                n_frames = wav.getnframes()

                if framerate != self.SAMPLE_RATE:
                    raise ValueError(
                        f"Audio must be {self.SAMPLE_RATE}Hz, got {framerate}Hz. "
                        f"Resample with: ffmpeg -i input.wav -ar 8000 output.wav"
                    )

                if channels != 1:
                    raise ValueError(
                        f"Audio must be mono, got {channels} channels. "
                        f"Convert with: ffmpeg -i input.wav -ac 1 output.wav"
                    )

                if sample_width != 2:
                    raise ValueError(
                        f"Audio must be 16-bit, got {sample_width*8}-bit"
                    )

                # Read all frames
                raw_data = wav.readframes(n_frames)

                # Convert to numpy int16 array
                self.audio_data = np.frombuffer(raw_data, dtype=np.int16).copy()

        except wave.Error as e:
            raise ValueError(f"Failed to read WAV file: {e}")

    def on_timer(self, t_ms: int) -> None:
        """Timer callback - nothing to do for file playback."""
        pass

    def push_tx_block(self, t_ms: int) -> np.ndarray:
        """Return the next block of audio samples.

        Returns exactly 160 samples (20ms at 8kHz).
        """
        if self.audio_data is None:
            return np.zeros(self.BLOCK_SIZE, dtype=np.int16)

        # Get current block
        end_pos = self.position + self.BLOCK_SIZE

        if end_pos <= len(self.audio_data):
            # Normal case - full block available
            block = self.audio_data[self.position:end_pos].copy()
            self.position = end_pos
        else:
            # End of file
            remaining = len(self.audio_data) - self.position
            block = np.zeros(self.BLOCK_SIZE, dtype=np.int16)

            if remaining > 0:
                block[:remaining] = self.audio_data[self.position:]

            if self.loop:
                # Wrap around and fill rest from beginning
                wrap_needed = self.BLOCK_SIZE - remaining
                if wrap_needed > 0 and len(self.audio_data) > 0:
                    block[remaining:] = self.audio_data[:wrap_needed]
                self.position = wrap_needed
            else:
                # No loop - stay at end (will output silence)
                self.position = len(self.audio_data)

        return block.astype(np.int16)

    def pull_rx_block(self, pcm: np.ndarray, t_ms: int) -> None:
        """Receive processed audio block.

        This stores received audio for potential quality analysis.
        """
        self.rx_count += 1
        # Optionally store for later analysis
        # self.rx_blocks.append(pcm.copy())

    def stop(self) -> None:
        """Stop the adapter."""
        if self.ctx:
            self.ctx.emit_event("audio_file_stats", {
                "blocks_sent": self.position // self.BLOCK_SIZE,
                "blocks_received": self.rx_count,
            })

    def get_playback_position(self) -> float:
        """Get current playback position as percentage (0-100)."""
        if self.audio_data is None or len(self.audio_data) == 0:
            return 0.0
        return (self.position / len(self.audio_data)) * 100.0


# Alias for compatibility
Adapter = AudioFileAdapter
