from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTextEdit, QProgressBar, QSplitter
)
from PySide6.QtCore import Qt
from datetime import datetime
from pathlib import Path
import tempfile
import yaml

from drybox.gui.runner.runner_thread import RunnerThread
from drybox.gui.widgets.metrics_graphs import (
    CombinedMetricsGraph, DualDirectionMetricsGraph, EnhancedCombinedMetricsGraph,
    SummaryStatsWidget
)


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
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # --- Main vertical splitter (graphs vs console) ---
        main_splitter = QSplitter(Qt.Vertical)

        # --- Top section: Graphs in horizontal splitter ---
        graphs_splitter = QSplitter(Qt.Horizontal)

        # Left panel: Enhanced metrics with all graphs
        left_graph_box = QGroupBox("Network Quality & Throughput")
        left_graph_layout = QVBoxLayout(left_graph_box)
        left_graph_layout.setContentsMargins(5, 5, 5, 5)
        self.left_metrics_graph = EnhancedCombinedMetricsGraph()
        left_graph_layout.addWidget(self.left_metrics_graph)
        graphs_splitter.addWidget(left_graph_box)

        # Right panel: Both directions comparison
        right_graph_box = QGroupBox("Direction Comparison (L→R vs R→L)")
        right_graph_layout = QVBoxLayout(right_graph_box)
        right_graph_layout.setContentsMargins(5, 5, 5, 5)
        self.right_metrics_graph = DualDirectionMetricsGraph()
        right_graph_layout.addWidget(self.right_metrics_graph)
        graphs_splitter.addWidget(right_graph_box)

        # Set initial sizes for horizontal splitter (50/50)
        graphs_splitter.setSizes([500, 500])

        main_splitter.addWidget(graphs_splitter)

        # --- Bottom section: Status + Progress + Log ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(5)

        # Status label
        self.status_label = QLabel("Ready")
        bottom_layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        bottom_layout.addWidget(self.progress_bar)

        # Log text box
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(100)
        bottom_layout.addWidget(self.log_text)

        main_splitter.addWidget(bottom_widget)

        # Set initial sizes for vertical splitter (70% graphs, 30% console)
        main_splitter.setSizes([700, 300])

        layout.addWidget(main_splitter)

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

        # Clear previous graph data
        self.left_metrics_graph.clear_data()
        self.right_metrics_graph.clear_data()

        try:
            # === Build schema-compliant scenario ===
            scenario_raw = self.general_page.to_dict()
            left_adapter, right_adapter = self.adapters_page.to_dict()
            left_info, right_info = self.adapters_page.get_selected_adapter_infos()

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

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # --- Output directory ---
            project_runs = Path(__file__).resolve().parents[3] / "runs"
            output_dir_path = project_runs / f"gui_{timestamp}"
            try:
                output_dir_path.mkdir(parents=True, exist_ok=True)
            except OSError:
                fallback_root = Path(tempfile.mkdtemp(prefix="drybox-run-"))
                output_dir_path = fallback_root / f"gui_{timestamp}"
                output_dir_path.mkdir(parents=True, exist_ok=True)
                self.append_log(f"Runs directory fallback -> {output_dir_path}")

            # === Scenario file alongside run artifacts ===
            scenario_path = output_dir_path / "scenario.gui.yaml"
            scenario_path.write_text(
                yaml.safe_dump(scenario, sort_keys=False),
                encoding="utf-8"
            )
            self.temp_scenario_file = str(scenario_path)

            # --- LOG THE GENERATED YAML ---
            scenario_contents = scenario_path.read_text(encoding="utf-8")
            self.append_log("Generated scenario.yaml contents:\n" + scenario_contents)

            output_dir = str(output_dir_path)

            self.append_log(f"Scenario file: {self.temp_scenario_file}")
            self.append_log(f"Left adapter: {left_info.display_name} -> {left_info.spec}")
            self.append_log(f"Right adapter: {right_info.display_name} -> {right_info.spec}")
            self.append_log(f"Output directory: {output_dir}")
            self.append_log("-" * 60)

            # Launch thread
            self.runner_thread = RunnerThread(
                self.temp_scenario_file,
                left_info.spec,
                right_info.spec,
                output_dir
            )
            self.runner_thread.log_signal.connect(self.append_log)
            self.runner_thread.status_signal.connect(lambda s: self.status_label.setText(s))
            self.runner_thread.progress_signal.connect(self.progress_bar.setValue)
            self.runner_thread.finished_signal.connect(self.on_run_finished)
            self.runner_thread.metrics_signal.connect(self._on_metrics_update)
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

        # Finalize summary statistics
        self.left_metrics_graph.finalize()

        if exit_code == 0:
            self.append_log("✓ Scenario completed successfully")
            self.status_label.setText("Completed")
        else:
            self.append_log(f"✗ Scenario failed with exit code: {exit_code}")
            self.status_label.setText("Failed")

        # Keep generated scenario artifacts; we only need to drop the handle here
        self.temp_scenario_file = None

    def _on_metrics_update(self, metrics: dict):
        """Handle real-time metrics updates from runner."""
        self.left_metrics_graph.update_metrics(metrics)
        self.right_metrics_graph.update_metrics(metrics)
