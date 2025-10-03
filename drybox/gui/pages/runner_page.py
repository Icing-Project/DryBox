from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTextEdit, QProgressBar
)
from datetime import datetime
import os, yaml

from drybox.gui.runner.runner_thread import RunnerThread


class RunnerPage(QWidget):
    """Runner page with graphs, log, status, and progress bar.
    Run/Stop buttons are handled in the navbar.
    """
    ALLOWED_KEYS = {"mode", "duration_ms", "seed", "network", "left", "right", "cfo_hz", "ppm", "crypto"}

    def __init__(self, general_page, adapters_page):
        super().__init__()
        self.general_page = general_page
        self.adapters_page = adapters_page
        self.runner_thread = None
        self.temp_scenario_file = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Graph placeholders ---
        graphs_layout = QHBoxLayout()
        graph_left = QGroupBox("Graph Left (placeholder)")
        graph_right = QGroupBox("Graph Right (placeholder)")
        graphs_layout.addWidget(graph_left)
        graphs_layout.addWidget(graph_right)
        layout.addLayout(graphs_layout)

        # --- Status label ---
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # --- Progress bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # --- Log text box ---
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

    # === Logging ===
    def append_log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    # === Runner logic ===
    def run_scenario(self):
        """Start scenario using RunnerThread"""
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.status_label.setText("Starting...")

        try:
            # === Build schema-compliant scenario ===
            scenario_raw = self.general_page.to_dict()
            left_adapter, right_adapter = self.adapters_page.to_dict()

            scenario = {
                "mode": scenario_raw.get("mode", "audio"),
                "duration_ms": scenario_raw.get("duration_ms", 5000),
                "seed": scenario_raw.get("seed", 123456),
                "network": scenario_raw.get("network", {}),
                "left": left_adapter,
                "right": right_adapter,
                "cfo_hz": scenario_raw.get("cfo_hz", 0),
                "ppm": scenario_raw.get("ppm", 0),
            }

            # --- Filter out any unexpected top-level keys ---
            scenario = {k: v for k, v in scenario.items() if k in self.ALLOWED_KEYS}

            # === Temp scenario file in drybox/scenarios ===
            scenarios_dir = os.path.join(os.path.dirname(__file__), "../../scenarios")
            os.makedirs(scenarios_dir, exist_ok=True)
            tmp_file_path = os.path.join(
                scenarios_dir, f"scenario_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
            )
            with open(tmp_file_path, "w") as f:
                yaml.dump(scenario, f, default_flow_style=False)
            self.temp_scenario_file = tmp_file_path

            # --- LOG THE GENERATED YAML ---
            with open(tmp_file_path, "r") as f:
                scenario_contents = f.read()
            self.append_log("Generated scenario.yaml contents:\n" + scenario_contents)

            # --- Output directory ---
            output_dir = os.path.join(
                os.path.dirname(__file__), "../../../runs",
                f"gui_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            os.makedirs(output_dir, exist_ok=True)

            self.append_log(f"Scenario file: {self.temp_scenario_file}")
            self.append_log(f"Left adapter: {left_adapter}")
            self.append_log(f"Right adapter: {right_adapter}")
            self.append_log(f"Output directory: {output_dir}")
            self.append_log("-" * 60)

            adapters_dir = os.path.join(os.path.dirname(__file__), "../../../adapters")
            left_filename = os.path.join(adapters_dir, left_adapter["adapter"])
            right_filename = os.path.join(adapters_dir, right_adapter["adapter"])


            # Launch thread
            self.runner_thread = RunnerThread(
                self.temp_scenario_file,
                left_filename,
                right_filename,
                output_dir
            )
            self.runner_thread.log_signal.connect(self.append_log)
            self.runner_thread.status_signal.connect(lambda s: self.status_label.setText(s))
            self.runner_thread.progress_signal.connect(self.progress_bar.setValue)
            self.runner_thread.finished_signal.connect(self.on_run_finished)
            self.runner_thread.start()

        except Exception as e:
            self.append_log(f"Error starting scenario: {e}")
            self.progress_bar.hide()
            self.status_label.setText("Error")


    def stop_scenario(self):
        """Stop running scenario"""
        if self.runner_thread and self.runner_thread.isRunning():
            self.runner_thread.stop()
            self.runner_thread.wait()
            self.status_label.setText("Stopped")
            self.progress_bar.hide()

    def on_run_finished(self, exit_code):
        """Handle runner completion"""
        self.runner_thread = None
        self.progress_bar.hide()

        if exit_code == 0:
            self.append_log("✓ Scenario completed successfully")
            self.status_label.setText("Completed")
        else:
            self.append_log(f"✗ Scenario failed with exit code: {exit_code}")
            self.status_label.setText("Failed")

        # Cleanup temp file
        if self.temp_scenario_file and os.path.exists(self.temp_scenario_file):
            try:
                os.unlink(self.temp_scenario_file)
            except Exception:
                pass
