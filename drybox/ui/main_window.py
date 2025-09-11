# Main window for DryBox UI
import sys
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtWidgets import QPushButton, QTextEdit, QLabel, QFileDialog
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

from ..core.runner import Runner
from .scenario_widget import ScenarioWidget


class RunnerThread(QThread):
    """Thread for running scenarios"""
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    
    def __init__(self, scenario_path: str):
        super().__init__()
        self.scenario_path = scenario_path
        self.runner: Optional[Runner] = None
        
    def run(self):
        """Run the scenario"""
        try:
            self.status_signal.emit("Loading scenario...")
            with open(self.scenario_path, 'r') as f:
                scenario_data = yaml.safe_load(f)
                
            self.runner = Runner()
            self.status_signal.emit("Running scenario...")
            
            # Run with event capture
            events = []
            self.runner.run_scenario(scenario_data, events=events)
            
            # Emit logs
            for event in events:
                self.log_signal.emit(f"{event['t_ms']:6d}ms [{event['side']}] {event['typ']}: {event.get('payload', {})}")
                
            self.status_signal.emit("Scenario completed")
            
        except Exception as e:
            self.status_signal.emit(f"Error: {str(e)}")
            self.log_signal.emit(f"Error running scenario: {str(e)}")
            
        finally:
            self.finished_signal.emit()


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.runner_thread: Optional[RunnerThread] = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize UI components"""
        self.setWindowTitle("DryBox - Logical Phone Call Emulator")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Top controls
        controls_layout = QHBoxLayout()
        main_layout.addLayout(controls_layout)
        
        # Load scenario button
        self.load_btn = QPushButton("Load Scenario")
        self.load_btn.clicked.connect(self.load_scenario)
        controls_layout.addWidget(self.load_btn)
        
        # Run button
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.run_scenario)
        self.run_btn.setEnabled(False)
        controls_layout.addWidget(self.run_btn)
        
        # Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_scenario)
        self.stop_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_btn)
        
        # Status label
        self.status_label = QLabel("No scenario loaded")
        controls_layout.addWidget(self.status_label)
        controls_layout.addStretch()
        
        # Scenario widget
        self.scenario_widget = ScenarioWidget()
        main_layout.addWidget(self.scenario_widget, stretch=1)
        
        # Log area
        log_label = QLabel("Event Log:")
        main_layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        main_layout.addWidget(self.log_text)
        
        # Current scenario path
        self.current_scenario_path: Optional[str] = None
        
    def load_scenario(self):
        """Load a scenario file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Scenario", 
            "scenarios/", 
            "YAML files (*.yaml *.yml)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    scenario_data = yaml.safe_load(f)
                    
                self.scenario_widget.load_scenario(scenario_data)
                self.current_scenario_path = file_path
                self.status_label.setText(f"Loaded: {Path(file_path).name}")
                self.run_btn.setEnabled(True)
                
            except Exception as e:
                self.status_label.setText(f"Error loading: {str(e)}")
                
    def run_scenario(self):
        """Run the current scenario"""
        if not self.current_scenario_path:
            return
            
        # Clear log
        self.log_text.clear()
        
        # Disable controls
        self.load_btn.setEnabled(False)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # Create and start runner thread
        self.runner_thread = RunnerThread(self.current_scenario_path)
        self.runner_thread.log_signal.connect(self.append_log)
        self.runner_thread.status_signal.connect(self.update_status)
        self.runner_thread.finished_signal.connect(self.on_run_finished)
        self.runner_thread.start()
        
    def stop_scenario(self):
        """Stop the running scenario"""
        if self.runner_thread and self.runner_thread.isRunning():
            self.runner_thread.terminate()
            self.runner_thread.wait()
            self.update_status("Scenario stopped")
            
    def append_log(self, message: str):
        """Append message to log"""
        self.log_text.append(message)
        
    def update_status(self, status: str):
        """Update status label"""
        self.status_label.setText(status)
        
    def on_run_finished(self):
        """Called when run finishes"""
        self.load_btn.setEnabled(True)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.runner_thread = None