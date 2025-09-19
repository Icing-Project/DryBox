from PySide6.QtCore import QThread, Signal
import subprocess, sys, os

class RunnerThread(QThread):
    log_signal = Signal(str)
    status_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(int)  # exit code

    def __init__(self, scenario_path: str, left_spec: str, right_spec: str, output_dir: str):
        super().__init__()
        self.scenario_path = scenario_path
        self.left_spec = left_spec
        self.right_spec = right_spec
        self.output_dir = output_dir
        self.process = None

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
                "--no-ui"
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

                    # Extract progress from t_ms=
                    if "t_ms=" in line:
                        try:
                            parts = line.split()
                            for part in parts:
                                if part.startswith("t_ms="):
                                    t_ms = int(part.split("=")[1])
                                    progress = min(100, int(t_ms / 50))
                                    self.progress_signal.emit(progress)
                        except:
                            pass

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
