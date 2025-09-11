#!/usr/bin/env python3
"""
Correct DryBox Configuration GUI
- Uses actual bearers and vocoders from the codebase
- Properly initializes and runs scenarios
- Generates adapter specs in the correct format
"""

import sys
import yaml
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    from PyQt6.QtWidgets import *
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
except ImportError:
    print("Error: PyQt6 is required")
    print("Install with: pip install PyQt6")
    sys.exit(1)


# Color scheme with better contrast
COLORS = {
    'bg_primary': '#1e1e1e',      # Darker, more neutral background
    'bg_secondary': '#2d2d30',    # Lighter secondary bg for better contrast
    'bg_tertiary': '#3e3e42',     # Even lighter for inputs
    'text': '#ffffff',            # Pure white for better contrast
    'text_secondary': '#b8b8b8',  # Brighter secondary text
    'accent': '#4a9eff',          # Brighter blue accent
    'accent_hover': '#6cb3ff',    # Lighter hover state
    'success': '#4ec9b0',         # Brighter success green
    'danger': '#f14c4c',          # Brighter red
    'warning': '#ffcc66',         # Brighter yellow
    'border': '#464647',          # Lighter border for visibility
}


def get_stylesheet():
    """Get stylesheet"""
    return f"""
    QMainWindow {{
        background-color: {COLORS['bg_primary']};
    }}
    
    QWidget {{
        background-color: {COLORS['bg_primary']};
        color: {COLORS['text']};
        font-family: -apple-system, 'Segoe UI', sans-serif;
        font-size: 14px;
    }}
    
    /* Group boxes */
    QGroupBox {{
        background-color: {COLORS['bg_secondary']};
        border: 2px solid {COLORS['border']};
        border-radius: 8px;
        margin-top: 24px;
        padding: 20px;
        padding-top: 30px;
        font-weight: 600;
        font-size: 15px;
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 10px;
        margin-left: 10px;
        color: {COLORS['accent']};
        background-color: {COLORS['bg_secondary']};
        font-weight: 600;
    }}
    
    /* Labels */
    QLabel {{
        color: {COLORS['text']};
        padding: 2px 0;
    }}
    
    /* Buttons */
    QPushButton {{
        background-color: {COLORS['accent']};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 20px;
        font-weight: 500;
        min-height: 36px;
    }}
    
    QPushButton:hover {{
        background-color: {COLORS['accent_hover']};
    }}
    
    QPushButton:disabled {{
        background-color: {COLORS['border']};
        color: {COLORS['text_secondary']};
    }}
    
    QPushButton#success {{
        background-color: {COLORS['success']};
    }}
    
    QPushButton#danger {{
        background-color: {COLORS['danger']};
    }}
    
    QPushButton#secondary {{
        background-color: transparent;
        border: 2px solid {COLORS['accent']};
        color: {COLORS['accent']};
    }}
    
    /* Inputs */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {COLORS['bg_tertiary']};
        border: 2px solid {COLORS['border']};
        border-radius: 4px;
        padding: 8px 12px;
        color: {COLORS['text']};
        min-height: 20px;
    }}
    
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {COLORS['accent']};
        border-width: 2px;
    }}
    
    /* ComboBox */
    QComboBox {{
        padding-right: 35px;
    }}
    
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 30px;
        border: none;
    }}
    
    QComboBox::down-arrow {{
        width: 0;
        height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {COLORS['accent']};
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_secondary']};
        border: 1px solid {COLORS['border']};
        selection-background-color: {COLORS['accent']};
    }}
    
    /* Radio buttons */
    QRadioButton {{
        spacing: 8px;
    }}
    
    /* Checkboxes */
    QCheckBox {{
        spacing: 8px;
    }}
    
    /* Text areas */
    QTextEdit {{
        background-color: {COLORS['bg_tertiary']};
        border: 2px solid {COLORS['border']};
        border-radius: 4px;
        padding: 8px;
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 13px;
        color: {COLORS['text']};
    }}
    
    /* Progress bar */
    QProgressBar {{
        background-color: {COLORS['bg_tertiary']};
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        text-align: center;
        height: 20px;
    }}
    
    QProgressBar::chunk {{
        background-color: {COLORS['accent']};
        border-radius: 3px;
    }}
    """


# Available components from the codebase
AVAILABLE_BEARERS = ["volte_evs", "cs_gsm", "pstn_g711", "ott_udp"]
AVAILABLE_VOCODERS = ["none", "amr12k2_mock", "evs13k2_mock", "opus_nb_mock"]
AVAILABLE_CHANNELS = ["none", "awgn", "fading"]


def get_available_adapters() -> Dict[str, str]:
    """Get available adapters with their class names"""
    adapters = {}
    
    # Check adapters directory
    adapter_dir = Path("adapters")
    if adapter_dir.exists():
        for file in adapter_dir.glob("*.py"):
            if file.name == "__init__.py":
                continue
            # Map file to expected class name
            if file.name == "audio_test.py":
                adapters["audio_test"] = "adapters/audio_test.py:AudioTestAdapter"
            elif file.name == "audio_wav_player.py":
                adapters["audio_wav_player"] = "adapters/audio_wav_player.py:AudioWavPlayer"
            elif file.name == "audio_recording_test.py":
                adapters["audio_recording_test"] = "adapters/audio_recording_test.py:AudioRecordingTest"
            elif file.name == "audio_enhanced_player.py":
                adapters["audio_enhanced_player"] = "adapters/audio_enhanced_player.py:AudioEnhancedPlayer"
            elif file.name == "pingpong.py":
                adapters["pingpong"] = "adapters/pingpong.py:PingPongAdapter"
                
    # Add built-in adapters
    adapters["echo"] = "drybox.adapters.echo:EchoAdapter"
    adapters["test"] = "drybox.adapters.test:TestAdapter"
    
    return adapters


class RunnerThread(QThread):
    """Thread for running scenarios via subprocess"""
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(int)  # exit code
    
    def __init__(self, scenario_path: str, left_spec: str, right_spec: str, output_dir: str):
        super().__init__()
        self.scenario_path = scenario_path
        self.left_spec = left_spec
        self.right_spec = right_spec
        self.output_dir = output_dir
        self.process = None
        
    def run(self):
        """Run the scenario using subprocess"""
        try:
            self.status_signal.emit("Starting DryBox runner...")
            
            # Build command
            cmd = [
                sys.executable,
                "-m", "drybox.core.runner",
                "--scenario", self.scenario_path,
                "--left", self.left_spec,
                "--right", self.right_spec,
                "--out", self.output_dir,
                "--no-ui"  # Disable UI mode for subprocess
            ]
            
            self.log_signal.emit(f"Running: {' '.join(cmd)}")
            self.status_signal.emit("Running scenario...")
            
            # Run process
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Read output line by line
            for line in self.process.stdout:
                line = line.strip()
                if line:
                    self.log_signal.emit(line)
                    
                    # Try to extract progress
                    if "t_ms=" in line:
                        try:
                            # Extract time from log
                            parts = line.split()
                            for part in parts:
                                if part.startswith("t_ms="):
                                    t_ms = int(part.split("=")[1])
                                    # Estimate progress (assuming 5000ms default duration)
                                    progress = min(100, int(t_ms / 50))
                                    self.progress_signal.emit(progress)
                        except:
                            pass
                            
            # Wait for process to complete
            exit_code = self.process.wait()
            
            if exit_code == 0:
                self.status_signal.emit("Scenario completed successfully")
            else:
                self.status_signal.emit(f"Scenario failed with exit code: {exit_code}")
                
            self.progress_signal.emit(100)
            self.finished_signal.emit(exit_code)
            
        except Exception as e:
            self.status_signal.emit(f"Error: {str(e)}")
            self.log_signal.emit(f"Error running scenario: {str(e)}")
            self.finished_signal.emit(-1)
            
    def stop(self):
        """Stop the running process"""
        if self.process:
            self.process.terminate()


class AdapterConfigWidget(QGroupBox):
    """Adapter configuration widget"""
    
    def __init__(self, side: str):
        super().__init__(f"Adapter {side}")
        self.side = side
        self.adapter_specs = get_available_adapters()
        self.config_widgets = {}
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Type selection
        type_layout = QHBoxLayout()
        layout.addLayout(type_layout)
        
        type_label = QLabel("Type:")
        type_label.setMinimumWidth(60)
        type_layout.addWidget(type_label)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(sorted(self.adapter_specs.keys()))
        self.type_combo.currentTextChanged.connect(self.update_config)
        type_layout.addWidget(self.type_combo)
        
        # Config area
        self.config_widget = QWidget()
        self.config_layout = QFormLayout(self.config_widget)
        self.config_layout.setSpacing(8)
        layout.addWidget(self.config_widget)
        
        # Set default
        if "audio_wav_player" in self.adapter_specs:
            self.type_combo.setCurrentText("audio_wav_player")
        elif "audio_test" in self.adapter_specs:
            self.type_combo.setCurrentText("audio_test")
            
    def update_config(self, adapter_type: str):
        """Update configuration UI"""
        # Clear existing
        while self.config_layout.count():
            item = self.config_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.config_widgets.clear()
        
        if adapter_type == "audio_test":
            freq_spin = QSpinBox()
            freq_spin.setRange(100, 10000)
            freq_spin.setValue(1000 if self.side == "L" else 800)
            freq_spin.setSuffix(" Hz")
            self.config_layout.addRow("Frequency:", freq_spin)
            self.config_widgets['frequency'] = freq_spin
            
        elif adapter_type == "audio_wav_player":
            # File selection
            file_widget = QWidget()
            file_layout = QHBoxLayout(file_widget)
            file_layout.setContentsMargins(0, 0, 0, 0)
            
            file_edit = QLineEdit()
            # Set default
            default_wav = f"WAV/{self.side}.wav"
            if Path(default_wav).exists():
                file_edit.setText(default_wav)
            file_edit.setPlaceholderText(f"Default: WAV/{self.side}.wav")
            
            browse_btn = QPushButton("Browse")
            browse_btn.clicked.connect(lambda: self.browse_file(file_edit))
            
            file_layout.addWidget(file_edit)
            file_layout.addWidget(browse_btn)
            
            self.config_layout.addRow("WAV File:", file_widget)
            self.config_widgets['file'] = file_edit
            
            loop_check = QCheckBox("Loop playback")
            self.config_layout.addRow("", loop_check)
            self.config_widgets['loop'] = loop_check
            
            gain_spin = QDoubleSpinBox()
            gain_spin.setRange(0.0, 2.0)
            gain_spin.setValue(1.0)
            gain_spin.setSingleStep(0.1)
            self.config_layout.addRow("Gain:", gain_spin)
            self.config_widgets['gain'] = gain_spin
            
        elif adapter_type == "audio_recording_test":
            signal_combo = QComboBox()
            signal_combo.addItems(["sine", "chirp", "noise", "silence"])
            self.config_layout.addRow("Signal:", signal_combo)
            self.config_widgets['signal_type'] = signal_combo
            
            record_check = QCheckBox("Enable recording")
            record_check.setChecked(True)
            self.config_layout.addRow("", record_check)
            self.config_widgets['recording'] = record_check
            
        elif adapter_type == "pingpong":
            start_check = QCheckBox("Start first")
            start_check.setChecked(self.side == "L")
            self.config_layout.addRow("", start_check)
            self.config_widgets['start'] = start_check
            
            interval_spin = QSpinBox()
            interval_spin.setRange(100, 10000)
            interval_spin.setValue(1000)
            interval_spin.setSuffix(" ms")
            self.config_layout.addRow("Interval:", interval_spin)
            self.config_widgets['interval_ms'] = interval_spin
            
    def browse_file(self, line_edit: QLineEdit):
        """Browse for WAV file"""
        start_dir = "WAV/" if Path("WAV/").exists() else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select WAV File", start_dir, "WAV files (*.wav)"
        )
        if file_path:
            line_edit.setText(file_path)
            
    def get_adapter_spec(self) -> str:
        """Get adapter spec string (e.g., 'adapters/audio_test.py:AudioTestAdapter')"""
        adapter_type = self.type_combo.currentText()
        return self.adapter_specs.get(adapter_type, adapter_type)
        
    def get_config(self) -> Dict[str, Any]:
        """Get adapter configuration for scenario file"""
        adapter_type = self.type_combo.currentText()
        config = {"type": adapter_type, "cfg": {}}
        
        if adapter_type == "audio_test":
            if 'frequency' in self.config_widgets:
                config["cfg"]["frequency"] = self.config_widgets['frequency'].value()
                
        elif adapter_type == "audio_wav_player":
            if 'file' in self.config_widgets:
                file_path = self.config_widgets['file'].text()
                if not file_path:
                    file_path = f"WAV/{self.side}.wav"
                config["cfg"]["file"] = file_path
            if 'loop' in self.config_widgets:
                config["cfg"]["loop"] = self.config_widgets['loop'].isChecked()
            if 'gain' in self.config_widgets:
                config["cfg"]["gain"] = self.config_widgets['gain'].value()
                
        elif adapter_type == "audio_recording_test":
            if 'signal_type' in self.config_widgets:
                config["cfg"]["signal_type"] = self.config_widgets['signal_type'].currentText()
            if 'recording' in self.config_widgets:
                config["cfg"]["recording"] = self.config_widgets['recording'].isChecked()
                
        elif adapter_type == "pingpong":
            if 'start' in self.config_widgets:
                config["cfg"]["start"] = self.config_widgets['start'].isChecked()
            if 'interval_ms' in self.config_widgets:
                config["cfg"]["interval_ms"] = self.config_widgets['interval_ms'].value()
                
        return config


class CorrectDryBoxGUI(QMainWindow):
    """Correct DryBox GUI with proper components"""
    
    def __init__(self):
        super().__init__()
        self.runner_thread = None
        self.temp_scenario_file = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("DryBox - Scenario Configuration")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1200, 700)
        
        # Apply stylesheet
        self.setStyleSheet(get_stylesheet())
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 20, 30, 20)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        main_layout.addWidget(scroll, 1)
        
        # Content
        content = QWidget()
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
        # Configuration sections
        config_layout = QHBoxLayout()
        content_layout.addLayout(config_layout)
        
        # Left column
        left_column = self.create_settings_column()
        config_layout.addWidget(left_column, 2)
        
        config_layout.addSpacing(20)
        
        # Right column
        right_column = self.create_adapters_column()
        config_layout.addWidget(right_column, 3)
        
        content_layout.addStretch()
        
        # Bottom section
        bottom = self.create_bottom_section()
        main_layout.addWidget(bottom)
        
    def create_header(self):
        """Create header"""
        header = QWidget()
        header.setMaximumHeight(60)
        layout = QHBoxLayout(header)
        
        title = QLabel("DryBox Scenario Configuration")
        title.setStyleSheet(f"font-size: 24px; font-weight: 600; color: {COLORS['text']};")
        layout.addWidget(title)
        
        layout.addStretch()
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(self.status_label)
        
        return header
        
    def create_settings_column(self):
        """Create settings column"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(20)
        
        # Basic settings
        basic_group = QGroupBox("Basic Settings")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(12)
        
        self.title_edit = QLineEdit("My Audio Scenario")
        basic_layout.addRow("Title:", self.title_edit)
        
        # Mode
        mode_widget = QWidget()
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(20)
        
        self.mode_audio = QRadioButton("Audio (Mode B)")
        self.mode_audio.setChecked(True)
        self.mode_bytelink = QRadioButton("ByteLink (Mode A)")
        
        mode_layout.addWidget(self.mode_audio)
        mode_layout.addWidget(self.mode_bytelink)
        mode_layout.addStretch()
        
        basic_layout.addRow("Mode:", mode_widget)
        
        # Duration
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(100, 60000)
        self.duration_spin.setValue(5000)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.setSingleStep(100)
        basic_layout.addRow("Duration:", self.duration_spin)
        
        # Seed
        seed_widget = QWidget()
        seed_layout = QHBoxLayout(seed_widget)
        seed_layout.setContentsMargins(0, 0, 0, 0)
        
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(0)
        self.seed_spin.setSpecialValueText("Random")
        seed_layout.addWidget(self.seed_spin)
        
        random_btn = QPushButton("Randomize")
        random_btn.clicked.connect(self.randomize_seed)
        seed_layout.addWidget(random_btn)
        seed_layout.addStretch()
        
        basic_layout.addRow("Seed:", seed_widget)
        
        layout.addWidget(basic_group)
        
        # Radio settings
        radio_group = QGroupBox("Radio Configuration")
        radio_layout = QFormLayout(radio_group)
        radio_layout.setSpacing(12)
        
        # Vocoder - using actual vocoders from the codebase
        self.vocoder_combo = QComboBox()
        self.vocoder_combo.addItems(AVAILABLE_VOCODERS)
        radio_layout.addRow("Vocoder:", self.vocoder_combo)
        
        # Channel
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(AVAILABLE_CHANNELS)
        self.channel_combo.currentTextChanged.connect(self.update_channel_params)
        radio_layout.addRow("Channel:", self.channel_combo)
        
        # Channel parameters
        self.channel_params_widget = QWidget()
        self.channel_params_layout = QFormLayout(self.channel_params_widget)
        self.channel_params_layout.setSpacing(8)
        radio_layout.addRow(self.channel_params_widget)
        
        layout.addWidget(radio_group)
        
        # Network settings
        net_group = QGroupBox("Network Configuration")
        net_layout = QFormLayout(net_group)
        net_layout.setSpacing(12)
        
        # Bearer type - using actual bearers from the codebase
        self.bearer_combo = QComboBox()
        self.bearer_combo.addItems(AVAILABLE_BEARERS)
        self.bearer_combo.currentTextChanged.connect(self.update_bearer_params)
        net_layout.addRow("Bearer:", self.bearer_combo)
        
        # Bearer parameters
        self.bearer_params_widget = QWidget()
        self.bearer_params_layout = QFormLayout(self.bearer_params_widget)
        self.bearer_params_layout.setSpacing(8)
        net_layout.addRow(self.bearer_params_widget)
        
        layout.addWidget(net_group)
        
        layout.addStretch()
        
        # Initialize params
        self.update_channel_params("awgn")
        self.update_bearer_params("volte_evs")
        
        return column
        
    def create_adapters_column(self):
        """Create adapters column"""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setSpacing(20)
        
        title = QLabel("Adapter Configuration")
        title.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {COLORS['accent']}; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Info about Mode B
        info = QLabel("Mode B (Audio) requires audio adapters on both sides")
        info.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(info)
        
        self.adapter_l = AdapterConfigWidget("L")
        layout.addWidget(self.adapter_l)
        
        self.adapter_r = AdapterConfigWidget("R")
        layout.addWidget(self.adapter_r)
        
        layout.addStretch()
        
        return column
        
    def create_bottom_section(self):
        """Create bottom section"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setSpacing(15)
        
        # Control buttons
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setSpacing(15)
        
        self.save_btn = QPushButton("Save Scenario")
        self.save_btn.setObjectName("secondary")
        self.save_btn.clicked.connect(self.save_scenario)
        controls_layout.addWidget(self.save_btn)
        
        self.load_btn = QPushButton("Load Scenario")
        self.load_btn.setObjectName("secondary")
        self.load_btn.clicked.connect(self.load_scenario)
        controls_layout.addWidget(self.load_btn)
        
        controls_layout.addStretch()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.hide()
        controls_layout.addWidget(self.progress_bar)
        
        self.run_btn = QPushButton("Run Scenario")
        self.run_btn.setObjectName("success")
        self.run_btn.clicked.connect(self.run_scenario)
        controls_layout.addWidget(self.run_btn)
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scenario)
        controls_layout.addWidget(self.stop_btn)
        
        layout.addWidget(controls)
        
        # Log area
        log_group = QGroupBox("Event Log")
        log_layout = QVBoxLayout(log_group)
        
        log_controls = QHBoxLayout()
        log_layout.addLayout(log_controls)
        
        log_controls.addWidget(QLabel("Runner Output:"))
        log_controls.addStretch()
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_log)
        log_controls.addWidget(clear_btn)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return section
        
    def update_channel_params(self, channel_type: str):
        """Update channel parameters"""
        # Clear existing
        while self.channel_params_layout.count():
            item = self.channel_params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        if channel_type == "none":
            # No parameters for none
            pass
        elif channel_type == "awgn":
            self.snr_spin = QSpinBox()
            self.snr_spin.setRange(-10, 50)
            self.snr_spin.setValue(20)
            self.snr_spin.setSuffix(" dB")
            self.channel_params_layout.addRow("SNR:", self.snr_spin)
            
        elif channel_type == "fading":
            self.snr_spin = QSpinBox()
            self.snr_spin.setRange(-10, 50)
            self.snr_spin.setValue(15)
            self.snr_spin.setSuffix(" dB")
            self.channel_params_layout.addRow("SNR:", self.snr_spin)
            
            self.doppler_spin = QDoubleSpinBox()
            self.doppler_spin.setRange(0.0, 1000.0)
            self.doppler_spin.setValue(10.0)
            self.doppler_spin.setSuffix(" Hz")
            self.channel_params_layout.addRow("Doppler (fd_hz):", self.doppler_spin)
            
            self.paths_spin = QSpinBox()
            self.paths_spin.setRange(1, 10)
            self.paths_spin.setValue(4)
            self.channel_params_layout.addRow("Paths (L):", self.paths_spin)
            
    def update_bearer_params(self, bearer_type: str):
        """Update bearer parameters"""
        # Clear existing
        while self.bearer_params_layout.count():
            item = self.bearer_params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        # Common parameters
        self.loss_spin = QDoubleSpinBox()
        self.loss_spin.setRange(0.0, 1.0)
        self.loss_spin.setValue(0.0)
        self.loss_spin.setSingleStep(0.01)
        self.bearer_params_layout.addRow("Loss Rate:", self.loss_spin)
        
        if bearer_type == "ott_udp":
            # OTT specific
            self.jitter_spin = QSpinBox()
            self.jitter_spin.setRange(0, 1000)
            self.jitter_spin.setValue(0)
            self.jitter_spin.setSuffix(" ms")
            self.bearer_params_layout.addRow("Jitter:", self.jitter_spin)
            
    def randomize_seed(self):
        """Generate random seed"""
        import random
        self.seed_spin.setValue(random.randint(1, 999999))
        
    def build_scenario(self) -> Dict[str, Any]:
        """Build scenario configuration"""
        scenario = {
            "mode": "audio" if self.mode_audio.isChecked() else "byte",
            "duration_ms": self.duration_spin.value(),
            "seed": self.seed_spin.value() if self.seed_spin.value() > 0 else 0,
        }
        
        # Bearer configuration (not 'net')
        bearer_type = self.bearer_combo.currentText()
        scenario["bearer"] = {
            "type": self.get_bearer_type_mapping(bearer_type),
            "loss_rate": self.loss_spin.value()
        }
        
        # Add bearer-specific parameters
        if bearer_type == "ott_udp":
            scenario["bearer"]["latency_ms"] = 20  # Default
            if hasattr(self, 'jitter_spin'):
                scenario["bearer"]["jitter_ms"] = self.jitter_spin.value()
            scenario["bearer"]["reorder_rate"] = 0.0
            scenario["bearer"]["mtu_bytes"] = 1500
            
        # Channel configuration (optional)
        channel_type = self.channel_combo.currentText()
        if channel_type and channel_type != "none":
            scenario["channel"] = {
                "type": channel_type
            }
            
            # Add channel parameters
            if channel_type == "awgn" and hasattr(self, 'snr_spin'):
                scenario["channel"]["snr_db"] = self.snr_spin.value()
            elif channel_type == "fading":
                if hasattr(self, 'snr_spin'):
                    scenario["channel"]["snr_db"] = self.snr_spin.value()
                if hasattr(self, 'doppler_spin'):
                    scenario["channel"]["fd_hz"] = self.doppler_spin.value()
                if hasattr(self, 'paths_spin'):
                    scenario["channel"]["L"] = self.paths_spin.value()
                
        # Vocoder configuration (optional)
        vocoder_type = self.vocoder_combo.currentText()
        if vocoder_type and vocoder_type != "none":
            scenario["vocoder"] = {
                "type": vocoder_type
            }
        
        return scenario
    
    def get_bearer_type_mapping(self, bearer_type: str) -> str:
        """Map GUI bearer names to schema bearer names"""
        mappings = {
            "volte_evs": "telco_volte_evs",
            "cs_gsm": "telco_cs_gsm", 
            "pstn_g711": "telco_pstn_g711",
            "ott_udp": "ott_udp"
        }
        return mappings.get(bearer_type, bearer_type)
        
    def save_scenario(self):
        """Save scenario to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Scenario", "scenarios/", "YAML files (*.yaml)"
        )
        
        if file_path:
            try:
                scenario = self.build_scenario()
                with open(file_path, 'w') as f:
                    yaml.dump(scenario, f, default_flow_style=False)
                self.status_label.setText(f"Saved: {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")
                
    def load_scenario(self):
        """Load scenario from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Scenario", "scenarios/", "YAML files (*.yaml *.yml)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    scenario = yaml.safe_load(f)
                    
                # Apply to UI (simplified)
                self.title_edit.setText(scenario.get("title", ""))
                if "duration_ms" in scenario:
                    self.duration_spin.setValue(scenario["duration_ms"])
                if "seed" in scenario and scenario["seed"]:
                    self.seed_spin.setValue(scenario["seed"])
                    
                # Mode
                mode = scenario.get("mode", "audio")
                if mode == "audio":
                    self.mode_audio.setChecked(True)
                else:
                    self.mode_bytelink.setChecked(True)
                    
                # Vocoder
                if "vocoder" in scenario and "type" in scenario["vocoder"]:
                    vocoder = scenario["vocoder"]["type"]
                    if vocoder in AVAILABLE_VOCODERS:
                        self.vocoder_combo.setCurrentText(vocoder)
                        
                # Channel
                if "channel" in scenario and "type" in scenario["channel"]:
                    channel = scenario["channel"]["type"]
                    if channel in AVAILABLE_CHANNELS:
                        self.channel_combo.setCurrentText(channel)
                            
                # Bearer
                if "bearer" in scenario:
                    bearer = scenario["bearer"]
                    if "type" in bearer:
                        # Reverse map from schema names to GUI names
                        bearer_type = bearer["type"]
                        gui_bearer_map = {
                            "telco_volte_evs": "volte_evs",
                            "telco_cs_gsm": "cs_gsm",
                            "telco_pstn_g711": "pstn_g711",
                            "ott_udp": "ott_udp"
                        }
                        gui_bearer = gui_bearer_map.get(bearer_type, bearer_type)
                        if gui_bearer in AVAILABLE_BEARERS:
                            self.bearer_combo.setCurrentText(gui_bearer)
                    if "loss_rate" in bearer:
                        self.loss_spin.setValue(bearer["loss_rate"])
                        
                self.status_label.setText(f"Loaded: {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load: {str(e)}")
                
    def run_scenario(self):
        """Run the scenario"""
        # Clear log
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        
        # Update UI
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        try:
            # Build scenario
            scenario = self.build_scenario()
            
            # Create temp scenario file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(scenario, f, default_flow_style=False)
                self.temp_scenario_file = f.name
                
            # Get adapter specs
            left_spec = self.adapter_l.get_adapter_spec()
            right_spec = self.adapter_r.get_adapter_spec()
            
            # Output directory
            output_dir = f"runs/gui_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            self.append_log(f"Scenario file: {self.temp_scenario_file}")
            self.append_log(f"Left adapter: {left_spec}")
            self.append_log(f"Right adapter: {right_spec}")
            self.append_log(f"Output directory: {output_dir}")
            self.append_log("-" * 60)
            
            # Create and start runner thread
            self.runner_thread = RunnerThread(
                self.temp_scenario_file,
                left_spec,
                right_spec,
                output_dir
            )
            self.runner_thread.log_signal.connect(self.append_log)
            self.runner_thread.status_signal.connect(lambda s: self.status_label.setText(s))
            self.runner_thread.progress_signal.connect(self.progress_bar.setValue)
            self.runner_thread.finished_signal.connect(self.on_run_finished)
            self.runner_thread.start()
            
        except Exception as e:
            self.append_log(f"Error starting scenario: {str(e)}")
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_bar.hide()
            
    def stop_scenario(self):
        """Stop running scenario"""
        if self.runner_thread and self.runner_thread.isRunning():
            self.runner_thread.stop()
            self.runner_thread.wait()
            self.status_label.setText("Stopped")
            
    def append_log(self, message: str):
        """Append message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def clear_log(self):
        """Clear the log"""
        self.log_text.clear()
        
    def on_run_finished(self, exit_code: int):
        """Called when run finishes"""
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.hide()
        self.runner_thread = None
        
        if exit_code == 0:
            self.append_log("✓ Scenario completed successfully")
        else:
            self.append_log(f"✗ Scenario failed with exit code: {exit_code}")
            
        # Clean up temp file
        if self.temp_scenario_file and os.path.exists(self.temp_scenario_file):
            try:
                os.unlink(self.temp_scenario_file)
            except:
                pass


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = CorrectDryBoxGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()