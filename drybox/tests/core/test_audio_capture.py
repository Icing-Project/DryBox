"""
Unit tests for AudioCaptureWriter.

Tests WAV file creation, streaming writes, format validation, and cleanup.
"""

import tempfile
import wave
from pathlib import Path
import numpy as np
import pytest

from drybox.core.audio_capture import AudioCaptureWriter, SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH, BLOCK_SIZE


class TestAudioCaptureWriter:
    """Test suite for AudioCaptureWriter class."""

    def test_audio_capture_creates_directory(self):
        """Verify that AudioCaptureWriter creates the audio/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            assert not audio_dir.exists()

            writer = AudioCaptureWriter(audio_dir)
            writer.close()

            assert audio_dir.exists()
            assert audio_dir.is_dir()

    def test_audio_capture_creates_four_files(self):
        """Verify that all 4 WAV files are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)
            writer.close()

            expected_files = ["left_tx.wav", "left_rx.wav", "right_tx.wav", "right_rx.wav"]
            for filename in expected_files:
                filepath = audio_dir / filename
                assert filepath.exists(), f"Expected file {filename} not found"
                assert filepath.stat().st_size > 0, f"File {filename} is empty"

    def test_audio_capture_wav_format(self):
        """Verify that WAV files have correct format (8kHz, mono, int16)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)
            writer.close()

            # Check each file's format
            for side in ["left", "right"]:
                for direction in ["tx", "rx"]:
                    filepath = audio_dir / f"{side}_{direction}.wav"
                    with wave.open(str(filepath), "rb") as wav:
                        assert wav.getnchannels() == CHANNELS, f"Expected {CHANNELS} channel(s)"
                        assert wav.getsampwidth() == SAMPLE_WIDTH, f"Expected sample width {SAMPLE_WIDTH}"
                        assert wav.getframerate() == SAMPLE_RATE, f"Expected sample rate {SAMPLE_RATE}"

    def test_audio_capture_write_tx_rx(self):
        """Test writing TX and RX audio blocks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)

            # Create sample audio data (160 samples = 20ms at 8kHz)
            pcm_data = np.random.randint(-32768, 32767, size=BLOCK_SIZE, dtype=np.int16)

            # Write to left TX
            writer.write_tx("left", pcm_data, t_ms=0)

            # Write to right RX
            writer.write_rx("right", pcm_data, t_ms=20)

            writer.close()

            # Verify left_tx.wav has data
            left_tx_path = audio_dir / "left_tx.wav"
            with wave.open(str(left_tx_path), "rb") as wav:
                frames = wav.readframes(wav.getnframes())
                assert len(frames) == BLOCK_SIZE * SAMPLE_WIDTH

            # Verify right_rx.wav has data
            right_rx_path = audio_dir / "right_rx.wav"
            with wave.open(str(right_rx_path), "rb") as wav:
                frames = wav.readframes(wav.getnframes())
                assert len(frames) == BLOCK_SIZE * SAMPLE_WIDTH

    def test_audio_capture_streaming(self):
        """Test incremental streaming writes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)

            # Write multiple blocks incrementally
            num_blocks = 10
            for i in range(num_blocks):
                pcm_data = np.random.randint(-32768, 32767, size=BLOCK_SIZE, dtype=np.int16)
                writer.write_tx("left", pcm_data, t_ms=i * 20)

            writer.close()

            # Verify total frames written
            left_tx_path = audio_dir / "left_tx.wav"
            with wave.open(str(left_tx_path), "rb") as wav:
                total_frames = wav.getnframes()
                expected_frames = num_blocks * BLOCK_SIZE
                assert total_frames == expected_frames, f"Expected {expected_frames} frames, got {total_frames}"

    def test_audio_capture_close_finalizes(self):
        """Verify that close() properly finalizes WAV files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)

            # Write some data
            pcm_data = np.random.randint(-32768, 32767, size=BLOCK_SIZE, dtype=np.int16)
            writer.write_tx("left", pcm_data, t_ms=0)

            # Close should finalize headers
            writer.close()

            # Verify file is valid and can be opened
            left_tx_path = audio_dir / "left_tx.wav"
            with wave.open(str(left_tx_path), "rb") as wav:
                assert wav.getnframes() == BLOCK_SIZE
                frames = wav.readframes(BLOCK_SIZE)
                assert len(frames) == BLOCK_SIZE * SAMPLE_WIDTH

    def test_audio_capture_read_back(self):
        """Write audio data and read it back to verify integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)

            # Create known pattern
            original_data = np.array([1000, 2000, -1000, -2000, 0] * 32, dtype=np.int16)
            writer.write_tx("left", original_data, t_ms=0)
            writer.close()

            # Read back
            left_tx_path = audio_dir / "left_tx.wav"
            with wave.open(str(left_tx_path), "rb") as wav:
                frames = wav.readframes(len(original_data))
                read_data = np.frombuffer(frames, dtype=np.int16)

            # Verify data integrity
            np.testing.assert_array_equal(original_data, read_data)

    def test_audio_capture_context_manager(self):
        """Test using AudioCaptureWriter as a context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"

            with AudioCaptureWriter(audio_dir) as writer:
                pcm_data = np.random.randint(-32768, 32767, size=BLOCK_SIZE, dtype=np.int16)
                writer.write_tx("left", pcm_data, t_ms=0)

            # Files should be closed and valid
            left_tx_path = audio_dir / "left_tx.wav"
            with wave.open(str(left_tx_path), "rb") as wav:
                assert wav.getnframes() == BLOCK_SIZE

    def test_audio_capture_multiple_writes_different_sides(self):
        """Test writing to all 4 files with realistic simulation pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)

            # Simulate bidirectional audio flow
            num_frames = 50  # 1 second at 20ms per frame
            for i in range(num_frames):
                t_ms = i * 20

                # Generate different patterns for each side
                left_pcm = np.full(BLOCK_SIZE, i % 1000, dtype=np.int16)
                right_pcm = np.full(BLOCK_SIZE, (i + 500) % 1000, dtype=np.int16)

                # TX on both sides
                writer.write_tx("left", left_pcm, t_ms)
                writer.write_tx("right", right_pcm, t_ms)

                # RX on both sides (with processing delay simulation)
                writer.write_rx("right", left_pcm, t_ms)
                writer.write_rx("left", right_pcm, t_ms)

            writer.close()

            # Verify all files have correct number of frames
            for side in ["left", "right"]:
                for direction in ["tx", "rx"]:
                    filepath = audio_dir / f"{side}_{direction}.wav"
                    with wave.open(str(filepath), "rb") as wav:
                        assert wav.getnframes() == num_frames * BLOCK_SIZE

    def test_audio_capture_empty_writes_after_close(self):
        """Verify that writes after close() are silently ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)

            # Write some data
            pcm_data = np.random.randint(-32768, 32767, size=BLOCK_SIZE, dtype=np.int16)
            writer.write_tx("left", pcm_data, t_ms=0)
            writer.close()

            # Try to write after close (should be silently ignored)
            writer.write_tx("left", pcm_data, t_ms=20)

            # Verify only original data was written
            left_tx_path = audio_dir / "left_tx.wav"
            with wave.open(str(left_tx_path), "rb") as wav:
                assert wav.getnframes() == BLOCK_SIZE

    def test_audio_capture_zero_samples(self):
        """Test behavior with zero-length audio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)

            # Write empty array
            pcm_data = np.array([], dtype=np.int16)
            writer.write_tx("left", pcm_data, t_ms=0)
            writer.close()

            # File should still exist but have 0 frames
            left_tx_path = audio_dir / "left_tx.wav"
            with wave.open(str(left_tx_path), "rb") as wav:
                assert wav.getnframes() == 0

    def test_audio_capture_large_simulation(self):
        """Test with a longer simulation (10 seconds)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_dir = Path(tmpdir) / "audio"
            writer = AudioCaptureWriter(audio_dir)

            # 10 seconds = 500 frames at 20ms per frame
            num_frames = 500
            for i in range(num_frames):
                pcm_data = np.random.randint(-32768, 32767, size=BLOCK_SIZE, dtype=np.int16)
                writer.write_tx("left", pcm_data, t_ms=i * 20)

            writer.close()

            # Verify duration
            left_tx_path = audio_dir / "left_tx.wav"
            with wave.open(str(left_tx_path), "rb") as wav:
                total_samples = wav.getnframes()
                duration_seconds = total_samples / SAMPLE_RATE
                assert abs(duration_seconds - 10.0) < 0.1  # Within 100ms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
