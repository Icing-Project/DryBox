# drybox/tests/test_integration_audio.py
# Integration tests for complete Mode B audio pipeline

import numpy as np
import pytest
import tempfile
import pathlib
import yaml
import shutil
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from drybox.core.runner import Runner, main
from drybox.core.scenario import ScenarioResolved
from drybox.core.metrics import MetricsWriter


class TestAudioIntegration:
    """Integration tests for Mode B audio features"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def audio_scenario(self, temp_dir):
        """Create a test audio scenario"""
        scenario = {
            "mode": "audio",
            "duration_ms": 1000,
            "seed": 42,
            "bearer": {
                "type": "ott_udp",
                "latency_ms": 20,
                "jitter_ms": 5,
                "loss_rate": 0.01,
                "reorder_rate": 0.0,
                "mtu_bytes": 1500
            }
        }
        scenario_path = pathlib.Path(temp_dir) / "test_scenario.yaml"
        with open(scenario_path, "w") as f:
            yaml.dump(scenario, f)
        return scenario_path
    
    def test_audio_loop_basic(self, temp_dir, audio_scenario):
        """Test basic audio loop functionality"""
        out_dir = pathlib.Path(temp_dir) / "run_output"
        
        runner = Runner(
            scenario=ScenarioResolved.from_yaml(audio_scenario),
            left_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            right_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            out_dir=out_dir,
            tick_ms=20,
            seed=42,
            ui_enabled=False
        )
        
        rc = runner.run()
        assert rc == 0
        
        # Check output files exist
        assert (out_dir / "metrics.csv").exists()
        assert (out_dir / "events.jsonl").exists()
        assert (out_dir / "capture.dbxcap").exists()
        # scenario.resolved.yaml is only created by CLI main(), not by Runner directly
    
    def test_audio_with_awgn(self, temp_dir):
        """Test audio with AWGN channel"""
        scenario = {
            "mode": "audio",
            "duration_ms": 500,
            "seed": 42,
            "bearer": {
                "type": "ott_udp",
                "latency_ms": 0,
                "jitter_ms": 0,
                "loss_rate": 0.0,
                "reorder_rate": 0.0,
                "mtu_bytes": 1500
            },
            "channel": {
                "type": "awgn",
                "snr_db": 10.0
            }
        }
        
        scenario_path = pathlib.Path(temp_dir) / "awgn_scenario.yaml"
        with open(scenario_path, "w") as f:
            yaml.dump(scenario, f)
        
        out_dir = pathlib.Path(temp_dir) / "run_awgn"
        
        runner = Runner(
            scenario=ScenarioResolved.from_yaml(scenario_path),
            left_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            right_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            out_dir=out_dir,
            tick_ms=20,
            seed=42,
            ui_enabled=False
        )
        
        rc = runner.run()
        assert rc == 0
        
        # Check SNR is recorded in metrics
        metrics_path = out_dir / "metrics.csv"
        with open(metrics_path, "r") as f:
            content = f.read()
            assert "snr_db_est" in content
    
    def test_audio_with_fading(self, temp_dir):
        """Test audio with Rayleigh fading channel"""
        scenario = {
            "mode": "audio",
            "duration_ms": 500,
            "seed": 42,
            "bearer": {
                "type": "ott_udp",
                "latency_ms": 0,
                "jitter_ms": 0,
                "loss_rate": 0.0,
                "reorder_rate": 0.0,
                "mtu_bytes": 1500
            },
            "channel": {
                "type": "fading",
                "snr_db": 15.0,
                "fd_hz": 50.0,
                "L": 8
            }
        }
        
        scenario_path = pathlib.Path(temp_dir) / "fading_scenario.yaml"
        with open(scenario_path, "w") as f:
            yaml.dump(scenario, f)
        
        out_dir = pathlib.Path(temp_dir) / "run_fading"
        
        runner = Runner(
            scenario=ScenarioResolved.from_yaml(scenario_path),
            left_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            right_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            out_dir=out_dir,
            tick_ms=20,
            seed=42,
            ui_enabled=False
        )
        
        rc = runner.run()
        assert rc == 0
    
    def test_audio_with_vocoder(self, temp_dir):
        """Test audio with vocoder processing"""
        scenario = {
            "mode": "audio",
            "duration_ms": 500,
            "seed": 42,
            "bearer": {
                "type": "ott_udp",
                "latency_ms": 0,
                "jitter_ms": 0,
                "loss_rate": 0.0,
                "reorder_rate": 0.0,
                "mtu_bytes": 1500
            },
            "vocoder": {
                "type": "amr12k2_mock",
                "vad_dtx": False
            }
        }
        
        scenario_path = pathlib.Path(temp_dir) / "vocoder_scenario.yaml"
        with open(scenario_path, "w") as f:
            yaml.dump(scenario, f)
        
        out_dir = pathlib.Path(temp_dir) / "run_vocoder"
        
        runner = Runner(
            scenario=ScenarioResolved.from_yaml(scenario_path),
            left_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            right_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            out_dir=out_dir,
            tick_ms=20,
            seed=42,
            ui_enabled=False
        )
        
        rc = runner.run()
        assert rc == 0
    
    def test_audio_with_plc(self, temp_dir):
        """Test audio with packet loss and PLC"""
        scenario = {
            "mode": "audio",
            "duration_ms": 500,
            "seed": 42,
            "bearer": {
                "type": "ott_udp",
                "latency_ms": 0,
                "jitter_ms": 0,
                "loss_rate": 0.1,  # 10% loss to trigger PLC
                "reorder_rate": 0.0,
                "mtu_bytes": 1500
            },
            "vocoder": {
                "type": "amr12k2_mock",
                "vad_dtx": False
            }
        }
        
        scenario_path = pathlib.Path(temp_dir) / "plc_scenario.yaml"
        with open(scenario_path, "w") as f:
            yaml.dump(scenario, f)
        
        out_dir = pathlib.Path(temp_dir) / "run_plc"
        
        runner = Runner(
            scenario=ScenarioResolved.from_yaml(scenario_path),
            left_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            right_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            out_dir=out_dir,
            tick_ms=20,
            seed=42,
            ui_enabled=False
        )
        
        rc = runner.run()
        assert rc == 0
        
        # Check that drops are recorded
        metrics_path = out_dir / "metrics.csv"
        with open(metrics_path, "r") as f:
            content = f.read()
            assert "drop" in content  # Should have drop events
    
    def test_full_pipeline(self, temp_dir):
        """Test complete audio pipeline with all features"""
        scenario = {
            "mode": "audio",
            "duration_ms": 500,
            "seed": 42,
            "bearer": {
                "type": "ott_udp",
                "latency_ms": 30,
                "jitter_ms": 10,
                "loss_rate": 0.02,
                "reorder_rate": 0.01,
                "mtu_bytes": 1500
            },
            "channel": {
                "type": "awgn",
                "snr_db": 15.0
            },
            "vocoder": {
                "type": "evs13k2_mock",
                "vad_dtx": True
            }
        }
        
        scenario_path = pathlib.Path(temp_dir) / "full_scenario.yaml"
        with open(scenario_path, "w") as f:
            yaml.dump(scenario, f)
        
        out_dir = pathlib.Path(temp_dir) / "run_full"
        
        runner = Runner(
            scenario=ScenarioResolved.from_yaml(scenario_path),
            left_adapter_spec="adapters/audio_test.py:AudioTestAdapter", 
            right_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            out_dir=out_dir,
            tick_ms=20,
            seed=42,
            ui_enabled=False
        )
        
        rc = runner.run()
        assert rc == 0
        
        # Verify all components are working
        events_path = out_dir / "events.jsonl"
        import json
        with open(events_path, "r") as f:
            events = [json.loads(line) for line in f]
        
        # Should have audio_rx events
        audio_events = [e for e in events if e.get("type") == "audio_rx"]
        assert len(audio_events) > 0
        
        # Check energy values exist
        energies = [e["payload"]["energy"] for e in audio_events]
        assert all(e > 0 for e in energies)
    
    def test_cli_interface(self, temp_dir, audio_scenario):
        """Test CLI interface for audio mode"""
        out_dir = pathlib.Path(temp_dir) / "cli_output"
        
        # Test with command line arguments
        argv = [
            "--scenario", str(audio_scenario),
            "--left", "adapters/audio_test.py:AudioTestAdapter",
            "--right", "adapters/audio_test.py:AudioTestAdapter",
            "--out", str(out_dir),
            "--tick-ms", "20",
            "--seed", "42",
            "--no-ui"
        ]
        
        rc = main(argv)
        assert rc == 0
        assert out_dir.exists()
        assert (out_dir / "metrics.csv").exists()

    def test_audio_export_end_to_end(self, temp_dir):
        """Test end-to-end audio export to WAV files"""
        scenario = {
            "mode": "audio",
            "duration_ms": 1000,  # 1 second
            "seed": 42,
            "network": {
                "bearer": "volte_evs",
                "latency_ms": 20,
                "jitter_ms": 5,
                "loss_rate": 0.01,
            },
            "left": {
                "modem": {
                    "channel_type": "awgn",
                    "snr_db": 20.0,
                    "vocoder": "evs13k2_mock",
                    "vad_dtx": False
                }
            },
            "right": {
                "modem": {}
            }
        }

        scenario_path = pathlib.Path(temp_dir) / "export_scenario.yaml"
        with open(scenario_path, "w") as f:
            yaml.dump(scenario, f)

        out_dir = pathlib.Path(temp_dir) / "run_export"

        runner = Runner(
            scenario=ScenarioResolved.from_yaml(scenario_path),
            left_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            right_adapter_spec="adapters/audio_test.py:AudioTestAdapter",
            out_dir=out_dir,
            tick_ms=1,  # 1ms ticks for continuous audio
            seed=42,
            ui_enabled=False
        )

        rc = runner.run()
        assert rc == 0

        # Check that audio folder was created
        audio_dir = out_dir / "audio"
        assert audio_dir.exists(), "audio/ directory should be created"
        assert audio_dir.is_dir(), "audio/ should be a directory"

        # Check that all 4 WAV files were created
        expected_files = ["left_tx.wav", "left_rx.wav", "right_tx.wav", "right_rx.wav"]
        for filename in expected_files:
            filepath = audio_dir / filename
            assert filepath.exists(), f"Expected file {filename} not found"
            assert filepath.stat().st_size > 0, f"File {filename} should not be empty"

        # Verify WAV file format and playability
        import wave
        for filename in expected_files:
            filepath = audio_dir / filename
            with wave.open(str(filepath), "rb") as wav:
                # Check format
                assert wav.getnchannels() == 1, f"{filename}: Expected mono audio"
                assert wav.getsampwidth() == 2, f"{filename}: Expected 16-bit samples"
                assert wav.getframerate() == 8000, f"{filename}: Expected 8kHz sample rate"

                # Check that frames were written
                num_frames = wav.getnframes()
                assert num_frames > 0, f"{filename}: No audio frames written"

                # Verify duration matches simulation (approximately)
                duration_seconds = num_frames / 8000.0
                expected_duration = 1.0  # 1000ms
                # Allow some tolerance for tick alignment
                assert 0.8 <= duration_seconds <= 1.2, \
                    f"{filename}: Duration {duration_seconds}s doesn't match expected ~{expected_duration}s"

                # Verify we can read the data
                frames = wav.readframes(num_frames)
                assert len(frames) == num_frames * 2, f"{filename}: Frame data size mismatch"

                # Convert to numpy and check it's valid audio data
                audio_data = np.frombuffer(frames, dtype=np.int16)
                assert len(audio_data) == num_frames, f"{filename}: Audio data length mismatch"
                assert audio_data.dtype == np.int16, f"{filename}: Audio data should be int16"

    def test_audio_export_byte_mode_skipped(self, temp_dir):
        """Verify that audio export is NOT created in byte mode"""
        scenario = {
            "mode": "byte",  # byte mode, not audio
            "duration_ms": 500,
            "seed": 42,
            "network": {
                "bearer": "ott_udp",
                "latency_ms": 20,
            }
        }

        scenario_path = pathlib.Path(temp_dir) / "byte_scenario.yaml"
        with open(scenario_path, "w") as f:
            yaml.dump(scenario, f)

        out_dir = pathlib.Path(temp_dir) / "run_byte"

        runner = Runner(
            scenario=ScenarioResolved.from_yaml(scenario_path),
            left_adapter_spec="adapters/test_traffic_adapter.py:TestTrafficAdapter",
            right_adapter_spec="adapters/test_traffic_adapter.py:TestTrafficAdapter",
            out_dir=out_dir,
            tick_ms=1,
            seed=42,
            ui_enabled=False
        )

        rc = runner.run()
        assert rc == 0

        # Verify audio folder was NOT created in byte mode
        audio_dir = out_dir / "audio"
        assert not audio_dir.exists(), "audio/ directory should NOT be created in byte mode"