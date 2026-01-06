"""Real-time metrics graph widgets using pyqtgraph."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
import pyqtgraph as pg
import numpy as np


class MetricsGraphWidget(QWidget):
    """Base widget for displaying real-time metrics graphs."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.max_points = 100  # Keep last 100 data points

        # Data storage
        self.time_data = []
        self.datasets = {}  # name -> list of values

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Configure pyqtgraph
        pg.setConfigOptions(antialias=True)

        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle(self.title, color='k', size='10pt')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend(offset=(10, 10))

        layout.addWidget(self.plot_widget)

        # Store plot curves
        self.curves = {}

    def add_series(self, name: str, color: str, symbol: str = None):
        """Add a new data series to the graph."""
        pen = pg.mkPen(color=color, width=2)
        if symbol:
            self.curves[name] = self.plot_widget.plot(
                [], [], pen=pen, name=name,
                symbol=symbol, symbolSize=5, symbolBrush=color
            )
        else:
            self.curves[name] = self.plot_widget.plot([], [], pen=pen, name=name)
        self.datasets[name] = []

    def add_data_point(self, t_ms: int, values: dict):
        """Add a data point for all series.

        Args:
            t_ms: Time in milliseconds
            values: Dict mapping series name to value
        """
        t_sec = t_ms / 1000.0
        self.time_data.append(t_sec)

        # Trim old data
        if len(self.time_data) > self.max_points:
            self.time_data = self.time_data[-self.max_points:]

        for name, value in values.items():
            if name in self.datasets:
                self.datasets[name].append(value)
                if len(self.datasets[name]) > self.max_points:
                    self.datasets[name] = self.datasets[name][-self.max_points:]

        self._update_plots()

    def _update_plots(self):
        """Update all plot curves with current data."""
        time_array = np.array(self.time_data)
        for name, curve in self.curves.items():
            if name in self.datasets and len(self.datasets[name]) > 0:
                data_array = np.array(self.datasets[name])
                # Ensure arrays are same length
                min_len = min(len(time_array), len(data_array))
                curve.setData(time_array[:min_len], data_array[:min_len])

    def clear_data(self):
        """Clear all data from the graph."""
        self.time_data = []
        for name in self.datasets:
            self.datasets[name] = []
        self._update_plots()


class NetworkMetricsGraph(MetricsGraphWidget):
    """Graph showing network metrics: loss rate, reorder rate."""

    def __init__(self, direction: str = "L→R", parent=None):
        super().__init__(f"Network Metrics ({direction})", parent)
        self.direction = direction

        # Add series for network metrics
        self.add_series('Loss Rate', '#e74c3c')  # Red
        self.add_series('Reorder Rate', '#f39c12')  # Orange

        # Set Y axis range for rates (0-1)
        self.plot_widget.setYRange(0, 1)
        self.plot_widget.setLabel('left', 'Rate', units='')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'byte':
            return

        t_ms = metrics.get('t_ms', 0)

        if self.direction == "L→R":
            values = {
                'Loss Rate': metrics.get('l2r_loss', 0),
                'Reorder Rate': metrics.get('l2r_reorder', 0),
            }
        else:
            values = {
                'Loss Rate': metrics.get('r2l_loss', 0),
                'Reorder Rate': metrics.get('r2l_reorder', 0),
            }

        self.add_data_point(t_ms, values)


class JitterMetricsGraph(MetricsGraphWidget):
    """Graph showing jitter metrics for both directions."""

    def __init__(self, parent=None):
        super().__init__("Jitter (ms)", parent)

        # Add series for jitter
        self.add_series('L→R Jitter', '#3498db')  # Blue
        self.add_series('R→L Jitter', '#9b59b6')  # Purple

        # Set Y axis
        self.plot_widget.setYRange(0, 50)
        self.plot_widget.setLabel('left', 'Jitter', units='ms')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'byte':
            return

        t_ms = metrics.get('t_ms', 0)
        values = {
            'L→R Jitter': metrics.get('l2r_jitter', 0),
            'R→L Jitter': metrics.get('r2l_jitter', 0),
        }
        self.add_data_point(t_ms, values)


class AudioModeGraph(MetricsGraphWidget):
    """Graph for audio mode - shows simulation progress."""

    def __init__(self, parent=None):
        super().__init__("Audio Mode Progress", parent)

        # Add series for audio activity
        self.add_series('Active', '#27ae60')  # Green

        # Set Y axis
        self.plot_widget.setYRange(0, 1.5)
        self.plot_widget.setLabel('left', 'Status', units='')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'audio':
            return

        t_ms = metrics.get('t_ms', 0)
        values = {
            'Active': 1.0,  # Just show activity
        }
        self.add_data_point(t_ms, values)


class CombinedMetricsGraph(QWidget):
    """Combined widget with two graph panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._current_mode = None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Create both graph types
        self.network_graph = NetworkMetricsGraph("L→R")
        self.jitter_graph = JitterMetricsGraph()
        self.audio_graph = AudioModeGraph()

        # Initially show network graphs
        layout.addWidget(self.network_graph)
        layout.addWidget(self.jitter_graph)

        # Hide audio graph initially
        self.audio_graph.setVisible(False)
        layout.addWidget(self.audio_graph)

    def update_metrics(self, metrics: dict):
        """Route metrics to appropriate graphs."""
        mode = metrics.get('mode')

        # Switch graph visibility based on mode
        if mode != self._current_mode:
            self._current_mode = mode
            if mode == 'byte':
                self.network_graph.setVisible(True)
                self.jitter_graph.setVisible(True)
                self.audio_graph.setVisible(False)
            elif mode == 'audio':
                self.network_graph.setVisible(False)
                self.jitter_graph.setVisible(False)
                self.audio_graph.setVisible(True)

        # Update the appropriate graphs
        if mode == 'byte':
            self.network_graph.update_metrics(metrics)
            self.jitter_graph.update_metrics(metrics)
        elif mode == 'audio':
            self.audio_graph.update_metrics(metrics)

    def clear_data(self):
        """Clear all graph data."""
        self.network_graph.clear_data()
        self.jitter_graph.clear_data()
        self.audio_graph.clear_data()
        self._current_mode = None


class DualDirectionMetricsGraph(QWidget):
    """Widget showing metrics for both L→R and R→L directions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._current_mode = None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Create graphs for both directions
        self.l2r_graph = NetworkMetricsGraph("L→R")
        self.r2l_graph = NetworkMetricsGraph("R→L")
        self.audio_graph = AudioModeGraph()

        layout.addWidget(self.l2r_graph)
        layout.addWidget(self.r2l_graph)

        # Hide audio graph initially
        self.audio_graph.setVisible(False)
        layout.addWidget(self.audio_graph)

    def update_metrics(self, metrics: dict):
        """Route metrics to appropriate graphs."""
        mode = metrics.get('mode')

        # Switch graph visibility based on mode
        if mode != self._current_mode:
            self._current_mode = mode
            if mode == 'byte':
                self.l2r_graph.setVisible(True)
                self.r2l_graph.setVisible(True)
                self.audio_graph.setVisible(False)
            elif mode == 'audio':
                self.l2r_graph.setVisible(False)
                self.r2l_graph.setVisible(False)
                self.audio_graph.setVisible(True)

        # Update the appropriate graphs
        if mode == 'byte':
            self.l2r_graph.update_metrics(metrics)
            # Update R→L graph
            self.r2l_graph.direction = "R→L"
            self.r2l_graph.update_metrics(metrics)
        elif mode == 'audio':
            self.audio_graph.update_metrics(metrics)

    def clear_data(self):
        """Clear all graph data."""
        self.l2r_graph.clear_data()
        self.r2l_graph.clear_data()
        self.audio_graph.clear_data()
        self._current_mode = None
