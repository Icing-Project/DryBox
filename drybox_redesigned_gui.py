#!/usr/bin/env python3
"""
DryBox Modern Professional GUI
A beautifully redesigned interface with modern aesthetics and improved UX
"""

import sys
import yaml
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

try:
    from PyQt6.QtWidgets import *
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
except ImportError:
    print("Error: PyQt6 is required")
    print("Install with: pip install PyQt6")
    sys.exit(1)


@dataclass
class Theme:
    """Modern color theme with carefully selected colors for professional appearance"""
    # Main background colors
    bg_primary: str = "#0A0E27"      # Deep dark blue - main background
    bg_secondary: str = "#151B3D"    # Slightly lighter - card backgrounds
    bg_tertiary: str = "#1E2649"     # Input backgrounds
    bg_hover: str = "#252E57"        # Hover state for cards
    
    # Accent colors
    accent_primary: str = "#6366F1"  # Modern purple-blue
    accent_secondary: str = "#818CF8" # Lighter accent
    accent_tertiary: str = "#A5B4FC"  # Even lighter for highlights
    
    # Text colors
    text_primary: str = "#F9FAFB"    # Pure white for main text
    text_secondary: str = "#9CA3AF"  # Muted gray for secondary text
    text_tertiary: str = "#6B7280"   # Even more muted for hints
    
    # Status colors
    success: str = "#10B981"         # Modern green
    warning: str = "#F59E0B"         # Amber warning
    danger: str = "#EF4444"          # Red for errors/stop
    info: str = "#3B82F6"            # Blue for info
    
    # UI element colors
    border: str = "#2D3561"          # Subtle borders
    border_focus: str = "#6366F1"    # Focus state borders
    shadow: str = "rgba(0, 0, 0, 0.5)"
    
    # Gradients
    gradient_start: str = "#6366F1"
    gradient_end: str = "#8B5CF6"


theme = Theme()


class ModernStyle:
    """Modern stylesheet generator with consistent design language"""
    
    @staticmethod
    def get_main_stylesheet() -> str:
        return f"""
        /* Main Window */
        QMainWindow {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 {theme.bg_primary},
                stop: 1 #0D1129
            );
        }}
        
        /* Base Widget Styling */
        QWidget {{
            color: {theme.text_primary};
            font-family: 'Inter', -apple-system, 'Segoe UI', system-ui, sans-serif;
            font-size: 14px;
        }}
        
        /* Modern Card-style Group Boxes */
        QGroupBox {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {theme.bg_secondary},
                stop: 1 rgba(21, 27, 61, 0.95)
            );
            border: 1px solid {theme.border};
            border-radius: 12px;
            margin-top: 28px;
            padding: 24px;
            padding-top: 36px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 24px;
            padding: 0 12px;
            color: {theme.accent_secondary};
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        
        /* Labels */
        QLabel {{
            color: {theme.text_primary};
            background: transparent;
        }}
        
        QLabel#heading {{
            font-size: 28px;
            font-weight: 700;
            color: {theme.text_primary};
            letter-spacing: -0.5px;
        }}
        
        QLabel#subheading {{
            font-size: 16px;
            font-weight: 500;
            color: {theme.text_secondary};
        }}
        
        QLabel#section-title {{
            font-size: 18px;
            font-weight: 600;
            color: {theme.accent_secondary};
            margin: 8px 0;
        }}
        
        QLabel#hint {{
            font-size: 12px;
            color: {theme.text_tertiary};
            font-style: italic;
        }}
        
        /* Modern Buttons */
        QPushButton {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {theme.accent_primary},
                stop: 1 {theme.gradient_end}
            );
            color: white;
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-weight: 600;
            font-size: 14px;
            min-height: 40px;
            letter-spacing: 0.3px;
        }}
        
        QPushButton:hover {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {theme.accent_secondary},
                stop: 1 {theme.accent_primary}
            );
        }}
        
        QPushButton:pressed {{
            background: {theme.gradient_end};
        }}
        
        QPushButton:disabled {{
            background: {theme.bg_tertiary};
            color: {theme.text_tertiary};
        }}
        
        /* Primary Action Button */
        QPushButton#primary {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 {theme.accent_primary},
                stop: 1 {theme.gradient_end}
            );
            font-size: 15px;
            min-height: 48px;
            padding: 14px 32px;
        }}
        
        QPushButton#primary:hover {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 {theme.accent_secondary},
                stop: 1 {theme.accent_primary}
            );
        }}
        
        /* Success Button */
        QPushButton#success {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {theme.success},
                stop: 1 #059669
            );
        }}
        
        QPushButton#success:hover {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #34D399,
                stop: 1 {theme.success}
            );
        }}
        
        /* Danger Button */
        QPushButton#danger {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 {theme.danger},
                stop: 1 #DC2626
            );
        }}
        
        QPushButton#danger:hover {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #F87171,
                stop: 1 {theme.danger}
            );
        }}
        
        /* Secondary/Outline Button */
        QPushButton#secondary {{
            background: transparent;
            border: 2px solid {theme.accent_primary};
            color: {theme.accent_secondary};
        }}
        
        QPushButton#secondary:hover {{
            background: rgba(99, 102, 241, 0.1);
            border-color: {theme.accent_secondary};
        }}
        
        /* Ghost Button */
        QPushButton#ghost {{
            background: transparent;
            color: {theme.text_secondary};
            border: none;
            padding: 8px 16px;
            min-height: 32px;
        }}
        
        QPushButton#ghost:hover {{
            background: rgba(99, 102, 241, 0.1);
            color: {theme.accent_secondary};
        }}
        
        /* Input Fields */
        QLineEdit, QSpinBox, QDoubleSpinBox {{
            background: {theme.bg_tertiary};
            border: 2px solid transparent;
            border-radius: 8px;
            padding: 10px 14px;
            color: {theme.text_primary};
            font-size: 14px;
            min-height: 24px;
        }}
        
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 2px solid {theme.accent_primary};
            background: rgba(99, 102, 241, 0.05);
        }}
        
        QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
            background: {theme.bg_hover};
        }}
        
        QLineEdit[readOnly="true"] {{
            background: {theme.bg_primary};
            color: {theme.text_tertiary};
        }}
        
        /* ComboBox */
        QComboBox {{
            background: {theme.bg_tertiary};
            border: 2px solid transparent;
            border-radius: 8px;
            padding: 10px 14px;
            padding-right: 40px;
            color: {theme.text_primary};
            font-size: 14px;
            min-height: 24px;
        }}
        
        QComboBox:focus {{
            border: 2px solid {theme.accent_primary};
            background: rgba(99, 102, 241, 0.05);
        }}
        
        QComboBox:hover {{
            background: {theme.bg_hover};
        }}
        
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 36px;
            border: none;
            background: transparent;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            width: 0;
            height: 0;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
            border-top: 8px solid {theme.accent_secondary};
        }}
        
        QComboBox QAbstractItemView {{
            background: {theme.bg_secondary};
            border: 1px solid {theme.border};
            border-radius: 8px;
            padding: 4px;
            selection-background-color: {theme.accent_primary};
            outline: none;
        }}
        
        QComboBox QAbstractItemView::item {{
            padding: 8px;
            min-height: 28px;
            border-radius: 4px;
        }}
        
        QComboBox QAbstractItemView::item:hover {{
            background: rgba(99, 102, 241, 0.2);
        }}
        
        /* Radio Buttons */
        QRadioButton {{
            spacing: 10px;
            color: {theme.text_primary};
            background: transparent;
        }}
        
        QRadioButton::indicator {{
            width: 20px;
            height: 20px;
            border: 2px solid {theme.border};
            border-radius: 10px;
            background: {theme.bg_tertiary};
        }}
        
        QRadioButton::indicator:hover {{
            border-color: {theme.accent_primary};
            background: {theme.bg_hover};
        }}
        
        QRadioButton::indicator:checked {{
            border-color: {theme.accent_primary};
            background: qradialgradient(
                cx: 0.5, cy: 0.5, radius: 0.5,
                fx: 0.5, fy: 0.5,
                stop: 0 {theme.accent_primary},
                stop: 0.4 {theme.accent_primary},
                stop: 0.5 {theme.bg_tertiary},
                stop: 1 {theme.bg_tertiary}
            );
        }}
        
        /* Checkboxes */
        QCheckBox {{
            spacing: 10px;
            color: {theme.text_primary};
            background: transparent;
        }}
        
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border: 2px solid {theme.border};
            border-radius: 4px;
            background: {theme.bg_tertiary};
        }}
        
        QCheckBox::indicator:hover {{
            border-color: {theme.accent_primary};
            background: {theme.bg_hover};
        }}
        
        QCheckBox::indicator:checked {{
            border-color: {theme.accent_primary};
            background: {theme.accent_primary};
            image: url(checkbox_checked.png);
        }}
        
        /* Text Edit / Log Area */
        QTextEdit {{
            background: {theme.bg_tertiary};
            border: 1px solid {theme.border};
            border-radius: 8px;
            padding: 12px;
            color: {theme.text_primary};
            font-family: 'JetBrains Mono', 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            line-height: 1.5;
        }}
        
        QTextEdit:focus {{
            border-color: {theme.accent_primary};
        }}
        
        /* Scroll Bars */
        QScrollBar:vertical {{
            background: {theme.bg_tertiary};
            width: 12px;
            border-radius: 6px;
            margin: 0;
        }}
        
        QScrollBar::handle:vertical {{
            background: {theme.border};
            border-radius: 6px;
            min-height: 30px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background: {theme.accent_primary};
        }}
        
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
            height: 0;
        }}
        
        /* Progress Bar */
        QProgressBar {{
            background: {theme.bg_tertiary};
            border: none;
            border-radius: 12px;
            height: 24px;
            text-align: center;
            color: {theme.text_primary};
            font-weight: 600;
            font-size: 12px;
        }}
        
        QProgressBar::chunk {{
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 {theme.accent_primary},
                stop: 1 {theme.gradient_end}
            );
            border-radius: 12px;
        }}
        
        /* Tabs */
        QTabWidget::pane {{
            background: {theme.bg_secondary};
            border: 1px solid {theme.border};
            border-radius: 8px;
            padding: 8px;
        }}
        
        QTabBar::tab {{
            background: transparent;
            color: {theme.text_secondary};
            padding: 10px 20px;
            margin-right: 4px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
        }}
        
        QTabBar::tab:hover {{
            background: rgba(99, 102, 241, 0.1);
            color: {theme.accent_secondary};
        }}
        
        QTabBar::tab:selected {{
            background: {theme.bg_secondary};
            color: {theme.text_primary};
            border: 1px solid {theme.border};
            border-bottom: none;
        }}
        
        /* Tooltips */
        QToolTip {{
            background: {theme.bg_secondary};
            color: {theme.text_primary};
            border: 1px solid {theme.accent_primary};
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 13px;
        }}
        
        /* Status Bar */
        QStatusBar {{
            background: {theme.bg_secondary};
            color: {theme.text_secondary};
            border-top: 1px solid {theme.border};
            padding: 4px;
        }}
        
        /* Separators */
        QFrame[frameShape="4"], QFrame[frameShape="5"] {{
            background: {theme.border};
            max-height: 1px;
            max-width: 1px;
        }}
        """


class AnimatedButton(QPushButton):
    """Custom animated button with smooth hover effects"""
    
    def __init__(self, text: str, style_name: str = None):
        super().__init__(text)
        self.style_name = style_name
        if style_name:
            self.setObjectName(style_name)
        
        # Animation setup
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    def enterEvent(self, event):
        """Animate on hover"""
        super().enterEvent(event)
        if self.isEnabled():
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            
    def leaveEvent(self, event):
        """Reset on leave"""
        super().leaveEvent(event)
        self.setCursor(Qt.CursorShape.ArrowCursor)


class ModernCard(QFrame):
    """Modern card widget with shadow and hover effects"""
    
    def __init__(self, title: str = None):
        super().__init__()
        self.title = title
        self.init_ui()
        
    def init_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {theme.bg_secondary};
                border: 1px solid {theme.border};
                border-radius: 12px;
                padding: 20px;
            }}
            QFrame:hover {{
                background: {theme.bg_hover};
                border-color: {theme.accent_primary};
            }}
        """)
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.setGraphicsEffect(shadow)


class StatusIndicator(QWidget):
    """Modern status indicator with animated pulse effect"""
    
    def __init__(self):
        super().__init__()
        self.status = "idle"
        self.init_ui()
        
    def init_ui(self):
        self.setFixedSize(12, 12)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Choose color based on status
        colors = {
            "idle": theme.text_tertiary,
            "ready": theme.success,
            "running": theme.accent_primary,
            "error": theme.danger
        }
        
        color = QColor(colors.get(self.status, theme.text_tertiary))
        
        # Draw outer glow for running state
        if self.status == "running":
            glow_color = QColor(color)
            glow_color.setAlpha(50)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow_color))
            painter.drawEllipse(0, 0, 12, 12)
        
        # Draw main circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(2, 2, 8, 8)
        
    def set_status(self, status: str):
        self.status = status
        self.update()


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
    """Modern adapter configuration widget"""
    
    def __init__(self, side: str):
        super().__init__(f"ADAPTER {side}")
        self.side = side
        self.adapter_specs = get_available_adapters()
        self.config_widgets = {}
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Type selection with icon
        type_widget = QWidget()
        type_layout = QHBoxLayout(type_widget)
        type_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_label = QLabel("📡")
        icon_label.setStyleSheet("font-size: 20px;")
        type_layout.addWidget(icon_label)
        
        type_label = QLabel("Type:")
        type_label.setStyleSheet(f"color: {theme.text_secondary}; font-weight: 500;")
        type_layout.addWidget(type_label)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(sorted(self.adapter_specs.keys()))
        self.type_combo.currentTextChanged.connect(self.update_config)
        type_layout.addWidget(self.type_combo, 1)
        
        layout.addWidget(type_widget)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background: {theme.border}; max-height: 1px;")
        layout.addWidget(separator)
        
        # Config area
        self.config_widget = QWidget()
        self.config_layout = QFormLayout(self.config_widget)
        self.config_layout.setSpacing(12)
        self.config_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
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
            
            browse_btn = AnimatedButton("📁", "ghost")
            browse_btn.setToolTip("Browse for WAV file")
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
        """Get adapter spec string"""
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


class ModernDryBoxGUI(QMainWindow):
    """Modern, beautiful DryBox GUI with enhanced UX"""
    
    def __init__(self):
        super().__init__()
        self.runner_thread = None
        self.temp_scenario_file = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("DryBox Professional")
        self.setGeometry(100, 100, 1500, 950)
        self.setMinimumSize(1300, 800)
        
        # Apply modern stylesheet
        self.setStyleSheet(ModernStyle.get_main_stylesheet())
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout with margins
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(24)
        main_layout.setContentsMargins(32, 24, 32, 24)
        
        # Header section
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Main content area
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setSpacing(24)
        
        # Left panel - Settings
        left_panel = self.create_left_panel()
        content_layout.addWidget(left_panel, 3)
        
        # Right panel - Adapters and Controls
        right_panel = self.create_right_panel()
        content_layout.addWidget(right_panel, 2)
        
        main_layout.addWidget(content_widget, 1)
        
        # Bottom section - Log output
        bottom_section = self.create_bottom_section()
        main_layout.addWidget(bottom_section)
        
        # Status bar
        self.create_status_bar()
        
    def create_header(self):
        """Create modern header with branding"""
        header = QWidget()
        header.setMaximumHeight(100)
        layout = QVBoxLayout(header)
        layout.setSpacing(8)
        
        # Top row
        top_row = QHBoxLayout()
        
        # Logo and title
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(16)
        
        # Logo placeholder
        logo_label = QLabel("🔊")
        logo_label.setStyleSheet("font-size: 32px;")
        title_layout.addWidget(logo_label)
        
        # Title and subtitle
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        
        title = QLabel("DryBox Professional")
        title.setObjectName("heading")
        text_layout.addWidget(title)
        
        subtitle = QLabel("Advanced Scenario Configuration & Testing Platform")
        subtitle.setObjectName("subheading")
        text_layout.addWidget(subtitle)
        
        title_layout.addWidget(text_widget)
        title_layout.addStretch()
        
        top_row.addWidget(title_widget)
        
        # Status indicator
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        
        self.status_indicator = StatusIndicator()
        self.status_indicator.set_status("ready")
        status_layout.addWidget(self.status_indicator)
        
        self.status_label = QLabel("System Ready")
        self.status_label.setStyleSheet(f"color: {theme.text_secondary}; font-weight: 500;")
        status_layout.addWidget(self.status_label)
        
        top_row.addWidget(status_widget)
        
        layout.addLayout(top_row)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background: {theme.border}; max-height: 2px; margin: 8px 0;")
        layout.addWidget(separator)
        
        return header
        
    def create_left_panel(self):
        """Create left panel with scenario settings"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(20)
        
        # Scenario settings tab widget
        tabs = QTabWidget()
        
        # Basic tab
        basic_tab = self.create_basic_settings_tab()
        tabs.addTab(basic_tab, "Basic")
        
        # Network tab
        network_tab = self.create_network_settings_tab()
        tabs.addTab(network_tab, "Network")
        
        # Radio tab
        radio_tab = self.create_radio_settings_tab()
        tabs.addTab(radio_tab, "Radio")
        
        layout.addWidget(tabs)
        
        return panel
        
    def create_basic_settings_tab(self):
        """Create basic settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(20)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Title
        self.title_edit = QLineEdit("My Audio Scenario")
        self.title_edit.setPlaceholderText("Enter scenario title...")
        layout.addRow("Title:", self.title_edit)
        
        # Mode selection with custom widget
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
        
        layout.addRow("Mode:", mode_widget)
        
        # Duration with slider
        duration_widget = QWidget()
        duration_layout = QHBoxLayout(duration_widget)
        duration_layout.setContentsMargins(0, 0, 0, 0)
        duration_layout.setSpacing(12)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(100, 60000)
        self.duration_spin.setValue(5000)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.setSingleStep(100)
        duration_layout.addWidget(self.duration_spin)
        
        duration_slider = QSlider(Qt.Orientation.Horizontal)
        duration_slider.setRange(100, 60000)
        duration_slider.setValue(5000)
        duration_slider.setSingleStep(100)
        duration_slider.valueChanged.connect(self.duration_spin.setValue)
        self.duration_spin.valueChanged.connect(duration_slider.setValue)
        duration_layout.addWidget(duration_slider, 1)
        
        layout.addRow("Duration:", duration_widget)
        
        # Seed with quick actions
        seed_widget = QWidget()
        seed_layout = QHBoxLayout(seed_widget)
        seed_layout.setContentsMargins(0, 0, 0, 0)
        seed_layout.setSpacing(8)
        
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(0)
        self.seed_spin.setSpecialValueText("Random")
        seed_layout.addWidget(self.seed_spin)
        
        random_btn = AnimatedButton("🎲 Randomize", "ghost")
        random_btn.clicked.connect(self.randomize_seed)
        seed_layout.addWidget(random_btn)
        
        seed_layout.addStretch()
        
        layout.addRow("Seed:", seed_widget)
        
        # Add some spacing
        spacer = QWidget()
        spacer.setFixedHeight(20)
        layout.addRow(spacer)
        
        # Info card
        info_card = ModernCard()
        info_layout = QVBoxLayout(info_card)
        
        info_title = QLabel("Quick Tips")
        info_title.setStyleSheet(f"color: {theme.accent_secondary}; font-weight: 600; margin-bottom: 8px;")
        info_layout.addWidget(info_title)
        
        info_text = QLabel("• Mode B (Audio) requires audio adapters\n"
                          "• Duration affects scenario runtime\n"
                          "• Use seed for reproducible tests")
        info_text.setObjectName("hint")
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)
        
        layout.addRow(info_card)
        
        return tab
        
    def create_network_settings_tab(self):
        """Create network settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(16)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Bearer type
        self.bearer_combo = QComboBox()
        self.bearer_combo.addItems(AVAILABLE_BEARERS)
        self.bearer_combo.currentTextChanged.connect(self.update_bearer_params)
        layout.addRow("Bearer Type:", self.bearer_combo)
        
        # Bearer parameters container
        self.bearer_params_widget = QWidget()
        self.bearer_params_layout = QFormLayout(self.bearer_params_widget)
        self.bearer_params_layout.setSpacing(12)
        layout.addRow(self.bearer_params_widget)
        
        # Initialize params
        self.update_bearer_params("volte_evs")
        
        return tab
        
    def create_radio_settings_tab(self):
        """Create radio settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(16)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Vocoder
        self.vocoder_combo = QComboBox()
        self.vocoder_combo.addItems(AVAILABLE_VOCODERS)
        layout.addRow("Vocoder:", self.vocoder_combo)
        
        # Channel
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(AVAILABLE_CHANNELS)
        self.channel_combo.currentTextChanged.connect(self.update_channel_params)
        layout.addRow("Channel:", self.channel_combo)
        
        # Channel parameters container
        self.channel_params_widget = QWidget()
        self.channel_params_layout = QFormLayout(self.channel_params_widget)
        self.channel_params_layout.setSpacing(12)
        layout.addRow(self.channel_params_widget)
        
        # Initialize params
        self.update_channel_params("awgn")
        
        return tab
        
    def create_right_panel(self):
        """Create right panel with adapters and controls"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(20)
        
        # Adapters section
        adapters_label = QLabel("ADAPTER CONFIGURATION")
        adapters_label.setObjectName("section-title")
        layout.addWidget(adapters_label)
        
        # Adapter cards
        self.adapter_l = AdapterConfigWidget("LEFT")
        layout.addWidget(self.adapter_l)
        
        self.adapter_r = AdapterConfigWidget("RIGHT")
        layout.addWidget(self.adapter_r)
        
        layout.addStretch()
        
        # Control section
        controls_label = QLabel("SCENARIO CONTROL")
        controls_label.setObjectName("section-title")
        layout.addWidget(controls_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Control buttons
        controls_widget = QWidget()
        controls_layout = QGridLayout(controls_widget)
        controls_layout.setSpacing(12)
        
        # Main actions
        self.run_btn = AnimatedButton("▶ Run Scenario", "primary")
        self.run_btn.clicked.connect(self.run_scenario)
        controls_layout.addWidget(self.run_btn, 0, 0, 1, 2)
        
        self.stop_btn = AnimatedButton("⏹ Stop", "danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scenario)
        controls_layout.addWidget(self.stop_btn, 1, 0, 1, 2)
        
        # File actions
        self.save_btn = AnimatedButton("💾 Save", "secondary")
        self.save_btn.clicked.connect(self.save_scenario)
        controls_layout.addWidget(self.save_btn, 2, 0)
        
        self.load_btn = AnimatedButton("📂 Load", "secondary")
        self.load_btn.clicked.connect(self.load_scenario)
        controls_layout.addWidget(self.load_btn, 2, 1)
        
        layout.addWidget(controls_widget)
        
        return panel
        
    def create_bottom_section(self):
        """Create bottom section with log output"""
        section = QGroupBox("EVENT LOG & OUTPUT")
        layout = QVBoxLayout(section)
        layout.setSpacing(12)
        
        # Log controls
        log_controls = QHBoxLayout()
        
        log_label = QLabel("System Output")
        log_label.setStyleSheet(f"color: {theme.text_secondary}; font-weight: 500;")
        log_controls.addWidget(log_label)
        
        log_controls.addStretch()
        
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        log_controls.addWidget(self.auto_scroll_check)
        
        clear_btn = AnimatedButton("Clear", "ghost")
        clear_btn.clicked.connect(self.clear_log)
        log_controls.addWidget(clear_btn)
        
        layout.addLayout(log_controls)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(250)
        self.log_text.setMinimumHeight(150)
        layout.addWidget(self.log_text)
        
        return section
        
    def create_status_bar(self):
        """Create custom status bar"""
        status_bar = self.statusBar()
        status_bar.setStyleSheet(f"""
            QStatusBar {{
                background: {theme.bg_secondary};
                color: {theme.text_secondary};
                border-top: 1px solid {theme.border};
                padding: 8px;
            }}
        """)
        status_bar.showMessage("Ready to configure and run scenarios")
        
    def update_channel_params(self, channel_type: str):
        """Update channel parameters"""
        # Clear existing
        while self.channel_params_layout.count():
            item = self.channel_params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        if channel_type == "awgn":
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
            self.channel_params_layout.addRow("Doppler:", self.doppler_spin)
            
            self.paths_spin = QSpinBox()
            self.paths_spin.setRange(1, 10)
            self.paths_spin.setValue(4)
            self.channel_params_layout.addRow("Paths:", self.paths_spin)
            
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
        
        # Bearer configuration
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
            
        # Channel configuration
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
                
        # Vocoder configuration
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
                self.statusBar().showMessage(f"Scenario saved to {file_path}", 3000)
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
                    
                # Apply to UI
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
                    
                self.status_label.setText(f"Loaded: {Path(file_path).name}")
                self.statusBar().showMessage(f"Scenario loaded from {file_path}", 3000)
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
        self.status_indicator.set_status("running")
        self.status_label.setText("Running scenario...")
        
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
            
            self.append_log(f"Scenario: {self.temp_scenario_file}")
            self.append_log(f"Left: {left_spec}")
            self.append_log(f"Right: {right_spec}")
            self.append_log(f"Output: {output_dir}")
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
            self.append_log(f"Error: {str(e)}")
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_bar.hide()
            self.status_indicator.set_status("error")
            
    def stop_scenario(self):
        """Stop running scenario"""
        if self.runner_thread and self.runner_thread.isRunning():
            self.runner_thread.stop()
            self.runner_thread.wait()
            self.status_label.setText("Stopped")
            self.status_indicator.set_status("ready")
            
    def append_log(self, message: str):
        """Append message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Color code based on message type
        if "Error" in message or "failed" in message:
            color = theme.danger
        elif "Success" in message or "completed" in message:
            color = theme.success
        elif "Warning" in message:
            color = theme.warning
        else:
            color = theme.text_primary
            
        formatted_msg = f'<span style="color: {theme.text_tertiary};">[{timestamp}]</span> '
        formatted_msg += f'<span style="color: {color};">{message}</span>'
        
        self.log_text.append(formatted_msg)
        
        # Auto-scroll if enabled
        if self.auto_scroll_check.isChecked():
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
            self.append_log("Scenario completed successfully")
            self.status_label.setText("Completed successfully")
            self.status_indicator.set_status("ready")
            self.statusBar().showMessage("Scenario execution completed", 3000)
        else:
            self.append_log(f"Scenario failed with exit code: {exit_code}")
            self.status_label.setText("Execution failed")
            self.status_indicator.set_status("error")
            self.statusBar().showMessage("Scenario execution failed", 3000)
            
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
    
    # Set application icon and metadata
    app.setApplicationName("DryBox Professional")
    app.setOrganizationName("DryBox Team")
    
    window = ModernDryBoxGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()