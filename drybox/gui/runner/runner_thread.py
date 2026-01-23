from PySide6.QtCore import QThread, Signal
import subprocess, sys, os
import re

class RunnerThread(QThread):
    log_signal = Signal(str)
    status_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(int)  # exit code
    metrics_signal = Signal(dict)  # real-time metrics data

    def __init__(self, scenario_path: str, left_spec: str, right_spec: str, output_dir: str):
        super().__init__()
        self.scenario_path = scenario_path
        self.left_spec = left_spec
        self.right_spec = right_spec
        self.output_dir = output_dir
        self.process = None
        self.duration_ms = self._parse_duration()

    def _parse_duration(self) -> int:
        """Parse duration_ms from scenario file"""
        try:
            import yaml
            with open(self.scenario_path, 'r') as f:
                scenario = yaml.safe_load(f)
                return scenario.get('duration_ms', 2000)
        except:
            return 5000

    def _parse_metrics_line(self, line: str) -> dict | None:
        """Parse metrics from runner output line.

        Byte mode format:
        [  1000 ms] L->R loss=0.000 reord=0.000 jitter=0.0ms | R->L loss=0.000 reord=0.000 jitter=0.0ms | rtt=120ms gp_l=1000bps gp_r=1000bps

        Audio mode format:
        [  1000 ms] Mode B Audio | snr=20.0dB ber=0.0010 per=0.050 frames=50 lost=2
        """
        # Pattern for byte mode metrics (extended with RTT and goodput)
        byte_pattern = (
            r'\[\s*(\d+)\s*ms\]\s*'
            r'L->R\s+loss=([\d.]+)\s+reord=([\d.]+)\s+jitter=([\d.]+)ms\s*\|\s*'
            r'R->L\s+loss=([\d.]+)\s+reord=([\d.]+)\s+jitter=([\d.]+)ms'
            r'(?:\s*\|\s*rtt=([\d.]+)ms\s+gp_l=([\d.]+)bps\s+gp_r=([\d.]+)bps)?'
        )
        match = re.search(byte_pattern, line)
        if match:
            result = {
                't_ms': int(match.group(1)),
                'mode': 'byte',
                'l2r_loss': float(match.group(2)),
                'l2r_reorder': float(match.group(3)),
                'l2r_jitter': float(match.group(4)),
                'r2l_loss': float(match.group(5)),
                'r2l_reorder': float(match.group(6)),
                'r2l_jitter': float(match.group(7)),
            }
            # Add optional extended metrics if present
            if match.group(8):
                result['rtt_ms'] = float(match.group(8))
            if match.group(9):
                result['goodput_l_bps'] = float(match.group(9))
            if match.group(10):
                result['goodput_r_bps'] = float(match.group(10))
            return result

        # Pattern for audio mode (extended with SNR, BER, PER, frames)
        # SNR can be 'inf' or a number like '20.0'
        audio_pattern = (
            r'\[\s*(\d+)\s*ms\]\s*Mode B Audio'
            r'(?:\s*\|\s*snr=([\d.inf-]+)dB\s+ber=([\d.]+)\s+per=([\d.]+)\s+'
            r'frames=(\d+)\s+lost=(\d+))?'
        )
        match = re.search(audio_pattern, line)
        if match:
            result = {
                't_ms': int(match.group(1)),
                'mode': 'audio',
            }
            # Add optional extended metrics if present
            if match.group(2):
                snr_str = match.group(2)
                if snr_str == 'inf' or snr_str == '-inf':
                    result['snr_db'] = 99.0 if snr_str == 'inf' else -99.0
                else:
                    result['snr_db'] = float(snr_str)
            if match.group(3):
                result['ber'] = float(match.group(3))
            if match.group(4):
                result['per'] = float(match.group(4))
            if match.group(5):
                result['frames_total'] = int(match.group(5))
            if match.group(6):
                result['frames_lost'] = int(match.group(6))
            return result

        return None

    def run(self):
        try:
            self.status_signal.emit("Starting runner...")
            cmd = [
                sys.executable,
                "-m", "drybox.core.runner",
                "--scenario", self.scenario_path,
                "--left", self.left_spec,
                "--right", self.right_spec,
                "--out", self.output_dir,
            ]
            self.log_signal.emit(f"Running: {' '.join(cmd)}")
            self.status_signal.emit("Running scenario...")

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in self.process.stdout:
                line = line.strip()
                if line:
                    self.log_signal.emit(line)

                    # Parse and emit metrics
                    metrics = self._parse_metrics_line(line)
                    if metrics:
                        self.metrics_signal.emit(metrics)
                        # Update progress based on actual time
                        t_ms = metrics.get('t_ms', 0)
                        if self.duration_ms > 0:
                            progress = min(100, int(100 * t_ms / self.duration_ms))
                            self.progress_signal.emit(progress)

            exit_code = self.process.wait()
            if exit_code == 0:
                self.status_signal.emit("Scenario completed successfully")
            else:
                self.status_signal.emit(f"Scenario failed with exit code: {exit_code}")
            self.progress_signal.emit(100)
            self.finished_signal.emit(exit_code)

        except Exception as e:
            self.status_signal.emit(f"Error: {e}")
            self.log_signal.emit(f"Error running scenario: {e}")
            self.finished_signal.emit(-1)

    def stop(self):
        if self.process:
            self.process.terminate()
