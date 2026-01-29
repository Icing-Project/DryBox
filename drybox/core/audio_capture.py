"""
Audio capture writer for exporting adapter audio as WAV files.

Streams audio blocks to disk during audio mode runs, creating 4 WAV files:
- left_tx.wav: Left adapter transmit (before processing)
- left_rx.wav: Left adapter receive (after processing)
- right_tx.wav: Right adapter transmit (before processing)
- right_rx.wav: Right adapter receive (after processing)
"""

import wave
from pathlib import Path
from typing import Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Audio flow parameters matching DryBox audio system
SAMPLE_RATE = 8000  # 8kHz narrowband
CHANNELS = 1        # Mono
SAMPLE_WIDTH = 2    # int16 = 2 bytes
BLOCK_SIZE = 160    # 20ms at 8kHz


class AudioCaptureWriter:
    """
    Streams adapter audio to WAV files during audio mode runs.

    Creates an audio/ subdirectory with 4 WAV files capturing bidirectional
    audio flow at adapter boundaries. Uses streaming writes for constant
    memory usage and crash resilience.
    """

    def __init__(self, audio_dir: Path):
        """
        Initialize audio capture writer.

        Args:
            audio_dir: Directory to create audio files in (typically runs/{timestamp}/audio)

        Raises:
            OSError: If directory creation or file opening fails
        """
        self.audio_dir = Path(audio_dir)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        # Initialize WAV file handles
        self.wav_files = {}
        self.files_open = False

        try:
            # Open all 4 WAV files for streaming writes
            for side in ['left', 'right']:
                for direction in ['tx', 'rx']:
                    key = f"{side}_{direction}"
                    path = self.audio_dir / f"{key}.wav"

                    wav_file = wave.open(str(path), 'wb')
                    wav_file.setnchannels(CHANNELS)
                    wav_file.setsampwidth(SAMPLE_WIDTH)
                    wav_file.setframerate(SAMPLE_RATE)

                    self.wav_files[key] = wav_file

            self.files_open = True
            logger.info(f"Audio capture initialized: {self.audio_dir}")

        except OSError as e:
            logger.error(f"Failed to initialize audio capture: {e}")
            self._cleanup_files()
            raise

    def write_tx(self, side: str, pcm: np.ndarray, t_ms: int):
        """
        Write transmit audio block (before adapter processing).

        Args:
            side: 'left' or 'right'
            pcm: Audio samples as int16 numpy array
            t_ms: Current simulation time in milliseconds
        """
        if not self.files_open:
            return

        key = f"{side}_tx"
        if key in self.wav_files:
            try:
                # Convert to bytes and write incrementally
                self.wav_files[key].writeframes(pcm.tobytes())
            except Exception as e:
                logger.warning(f"Failed to write {key} audio at t={t_ms}ms: {e}")

    def write_rx(self, side: str, pcm: np.ndarray, t_ms: int):
        """
        Write receive audio block (after adapter processing).

        Args:
            side: 'left' or 'right'
            pcm: Audio samples as int16 numpy array
            t_ms: Current simulation time in milliseconds
        """
        if not self.files_open:
            return

        key = f"{side}_rx"
        if key in self.wav_files:
            try:
                # Convert to bytes and write incrementally
                self.wav_files[key].writeframes(pcm.tobytes())
            except Exception as e:
                logger.warning(f"Failed to write {key} audio at t={t_ms}ms: {e}")

    def close(self):
        """
        Finalize and close all WAV files.

        Should be called at the end of the run to ensure proper WAV headers.
        """
        if not self.files_open:
            return

        self._cleanup_files()
        logger.info(f"Audio capture finalized: {len(self.wav_files)} files written")

    def _cleanup_files(self):
        """Close all open WAV file handles."""
        for key, wav_file in self.wav_files.items():
            try:
                wav_file.close()
            except Exception as e:
                logger.warning(f"Error closing {key}.wav: {e}")

        self.wav_files.clear()
        self.files_open = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure files are closed."""
        self.close()
        return False
