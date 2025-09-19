from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QMenu, QSizePolicy,
    QFileDialog, QMessageBox
)
from PySide6.QtGui import QAction

from drybox.gui.utils.helpers import (
    collect_scenario, apply_scenario,
    load_scenario_file, save_scenario_file,
    default_scenario_path, ensure_yaml_suffix
)

from .adapters_page import AdaptersPage
from .general_page import GeneralPage
from .runner_page import RunnerPage



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Network Audio Simulator")
        self.resize(1200, 800)
        self.current_scenario: Path | None = None

        # --- Pages ---
        self.stack = QStackedWidget()
        self.adapters_page = AdaptersPage()
        self.general_page = GeneralPage()
        self.runner_page = RunnerPage(self.general_page, self.adapters_page)
        self.stack.addWidget(self.adapters_page)
        self.stack.addWidget(self.general_page)
        self.stack.addWidget(self.runner_page)

        # --- Navbar ---
        navbar = QWidget()
        navbar_layout = QHBoxLayout(navbar)
        navbar_layout.setContentsMargins(8, 8, 8, 8)
        navbar_layout.setSpacing(6)

        # Navigation buttons
        nav_buttons = QHBoxLayout()
        self.btn_adapters = QPushButton("Adapters")
        self.btn_general = QPushButton("General")
        self.btn_runner = QPushButton("Runner")
        for btn in [self.btn_adapters, self.btn_general, self.btn_runner]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            nav_buttons.addWidget(btn)
        self.btn_adapters.clicked.connect(lambda: self.stack.setCurrentWidget(self.adapters_page))
        self.btn_general.clicked.connect(lambda: self.stack.setCurrentWidget(self.general_page))
        self.btn_runner.clicked.connect(lambda: self.stack.setCurrentWidget(self.runner_page))
        navbar_layout.addLayout(nav_buttons, 1)

        # Right side: Run / Stop / Scenario menu
        self.btn_run = QPushButton("Run")
        self.btn_run.setCheckable(True)
        self.btn_run.clicked.connect(self.on_run_clicked)
        navbar_layout.addWidget(self.btn_run)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.on_stop_clicked)
        navbar_layout.addWidget(self.btn_stop)

        self.btn_scenario = QPushButton("☰")
        menu = QMenu(self)
        self.action_load = QAction("Load Scenario", self)
        self.action_save = QAction("Save Scenario", self)
        self.action_save_as = QAction("Save Scenario As…", self)
        menu.addAction(self.action_load)
        menu.addAction(self.action_save)
        menu.addAction(self.action_save_as)
        self.btn_scenario.setMenu(menu)
        navbar_layout.addWidget(self.btn_scenario)

        # --- Main layout ---
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(navbar)
        layout.addWidget(self.stack)
        self.setCentralWidget(container)

        # Connect menu actions
        self.action_load.triggered.connect(self.load_scenario)
        self.action_save.triggered.connect(self.save_scenario)
        self.action_save_as.triggered.connect(self.save_scenario_as)

    # === Run / Stop logic ===
    def on_run_clicked(self, checked: bool):
        if checked:
            self.btn_run.setEnabled(False)
            self.btn_stop.setEnabled(True)
            self.stack.setCurrentWidget(self.runner_page)
            self.runner_page.run_scenario()
            if self.runner_page.runner_thread:
                self.runner_page.runner_thread.finished_signal.connect(self.on_runner_finished)

    def on_stop_clicked(self):
        self.runner_page.stop_scenario()
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def on_runner_finished(self, exit_code: int):
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    # === Scenario handling ===
    def load_scenario(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Scenario", str(default_scenario_path()), "YAML Files (*.yaml *.yml)"
        )
        if not path:
            return
        try:
            scenario = load_scenario_file(Path(path))
            apply_scenario(self.general_page, self.adapters_page, scenario)
            self.current_scenario = Path(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load scenario: {e}")

    def save_scenario(self):
        if not self.current_scenario:
            return self.save_scenario_as()
        scenario = collect_scenario(self.general_page, self.adapters_page)
        try:
            save_scenario_file(self.current_scenario, scenario)
            QMessageBox.information(self, "Scenario Saved", f"Saved to {self.current_scenario}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save scenario: {e}")

    def save_scenario_as(self):
        default_path = default_scenario_path()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Scenario As", str(default_path), "YAML Files (*.yaml *.yml)"
        )
        if not path:
            return
        path = ensure_yaml_suffix(Path(path))
        self.current_scenario = path
        self.save_scenario()
