"""Real-time metrics graph widgets using pyqtgraph."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import pyqtgraph as pg
import numpy as np

class IntAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        # values: list of float tick positions
        # Convert them to integers as strings (no decimals)
        return [str(int(value)) for value in values]


class MetricsGraphWidget(QWidget):
    """Base widget for displaying real-time metrics graphs."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.max_points = 1000  # Keep last 1000 data points

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
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': IntAxisItem(orientation='bottom')})
        self.plot_widget.setBackground('w')
        self.plot_widget.setTitle(self.title, color='k', size='10pt')
        self.plot_widget.setLabel('bottom', 'Time (ms)')
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
        self.time_data.append(t_ms)

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

        # Byte mode: Create graphs for both directions
        self.l2r_graph = NetworkMetricsGraph("L→R")
        self.r2l_graph = NetworkMetricsGraph("R→L")

        # Audio mode: Frame statistics graph
        self.frame_stats_graph = FrameStatsGraph()

        layout.addWidget(self.l2r_graph)
        layout.addWidget(self.r2l_graph)
        layout.addWidget(self.frame_stats_graph)

        # Initially show byte mode
        self.frame_stats_graph.setVisible(False)

    def update_metrics(self, metrics: dict):
        """Route metrics to appropriate graphs."""
        mode = metrics.get('mode')

        # Switch graph visibility based on mode
        if mode != self._current_mode:
            self._current_mode = mode
            if mode == 'byte':
                self.l2r_graph.setVisible(True)
                self.r2l_graph.setVisible(True)
                self.frame_stats_graph.setVisible(False)
            elif mode == 'audio':
                self.l2r_graph.setVisible(False)
                self.r2l_graph.setVisible(False)
                self.frame_stats_graph.setVisible(True)

        # Update the appropriate graphs
        if mode == 'byte':
            self.l2r_graph.update_metrics(metrics)
            # Update R→L graph
            self.r2l_graph.direction = "R→L"
            self.r2l_graph.update_metrics(metrics)
        elif mode == 'audio':
            self.frame_stats_graph.update_metrics(metrics)

    def clear_data(self):
        """Clear all graph data."""
        self.l2r_graph.clear_data()
        self.r2l_graph.clear_data()
        self.frame_stats_graph.clear_data()
        self._current_mode = None


class FrameStatsGraph(MetricsGraphWidget):
    """Graph showing frame statistics for audio mode (bytes sent vs lost) and bytes processed."""

    def __init__(self, parent=None):
        super().__init__("Frame & Data Statistics", parent)

        # Add series for frame counts
        self.add_series('Total Bytes (includes silence)', '#2ecc71')  # Green
        self.add_series('Total Lost Bytes (includes silence)', '#e74c3c')  # Red
        self.add_series('Total Bytes L', '#3498db')  # Blue
        self.add_series('Total Bytes R', '#9b59b6')  # Purple

        # Set Y axis (auto-scale)
        self.plot_widget.setYRange(0, 100)
        self.plot_widget.setLabel('left', 'Count', units='')
        self.plot_widget.enableAutoRange(axis='y')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'audio':
            return

        t_ms = metrics.get('t_ms', 0)
        values = {}

        total_bytes = metrics.get('total_bytes', 0)
        total_lost_bytes = metrics.get('total_lost_bytes', 0)
        total_bytes_l = metrics.get('total_bytes_l', 0)
        total_bytes_r = metrics.get('total_bytes_r', 0)

        if total_bytes > 0:
            values['Total Bytes (includes silence)'] = total_bytes
            values['Total Lost Bytes (includes silence)'] = total_lost_bytes
        
        if total_bytes_l > 0:
            values['Total Bytes L'] = total_bytes_l
        
        if total_bytes_r > 0:
            values['Total Bytes R'] = total_bytes_r

        if values:
            self.add_data_point(t_ms, values)


# ============================================================================
# NEW GRAPHS: Goodput, RTT, SNR, BER/PER, Summary Statistics
# ============================================================================


class GoodputGraph(MetricsGraphWidget):
    """Graph showing goodput (actual throughput) for both directions."""

    def __init__(self, parent=None):
        super().__init__("Goodput (Throughput)", parent)

        # Add series for goodput in both directions
        self.add_series('L→R Goodput', '#2ecc71')  # Green
        self.add_series('R→L Goodput', '#1abc9c')  # Teal

        # Set Y axis (auto-scale, but start at 0)
        self.plot_widget.setYRange(0, 10000)
        self.plot_widget.setLabel('left', 'Goodput', units='bps')
        self.plot_widget.enableAutoRange(axis='y')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'byte':
            return

        t_ms = metrics.get('t_ms', 0)
        values = {
            'L→R Goodput': metrics.get('goodput_l_bps', 0),
            'R→L Goodput': metrics.get('goodput_r_bps', 0),
        }
        self.add_data_point(t_ms, values)


class RTTGraph(MetricsGraphWidget):
    """Graph showing Round-Trip Time estimation."""

    def __init__(self, parent=None):
        super().__init__("Round-Trip Time (RTT)", parent)

        # Add series for RTT
        self.add_series('RTT', '#e67e22')  # Orange

        # Set Y axis range
        self.plot_widget.setYRange(0, 500)
        self.plot_widget.setLabel('left', 'RTT', units='ms')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'byte':
            return

        t_ms = metrics.get('t_ms', 0)
        rtt = metrics.get('rtt_ms', 0)
        if rtt > 0:
            values = {'RTT': rtt}
            self.add_data_point(t_ms, values)


class SNRGraph(MetricsGraphWidget):
    """Graph showing Signal-to-Noise Ratio for audio mode."""

    def __init__(self, parent=None):
        super().__init__("Signal-to-Noise Ratio (SNR)", parent)

        # Add series for SNR
        self.add_series('SNR', '#3498db')  # Blue

        # Set Y axis range (typical SNR range: -10 to 50 dB)
        self.plot_widget.setYRange(-10, 50)
        self.plot_widget.setLabel('left', 'SNR', units='dB')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'audio':
            return

        t_ms = metrics.get('t_ms', 0)
        snr = metrics.get('snr_db')
        if snr is not None:
            values = {'SNR': snr}
            self.add_data_point(t_ms, values)


class BERPERGraph(MetricsGraphWidget):
    """Graph showing Bit Error Rate (BER) and Packet Error Rate (PER) for audio mode."""

    def __init__(self, parent=None):
        super().__init__("Error Rates (BER/PER)", parent)

        # Add series for BER and PER
        self.add_series('BER', '#e74c3c')  # Red
        self.add_series('PER', '#9b59b6')  # Purple

        # Set Y axis range (0-1 for rates, but BER can be very small)
        self.plot_widget.setYRange(0, 0.5)
        self.plot_widget.setLabel('left', 'Error Rate', units='')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'audio':
            return

        t_ms = metrics.get('t_ms', 0)
        values = {}

        ber = metrics.get('ber')
        if ber is not None:
            values['BER'] = ber

        per = metrics.get('per')
        if per is not None:
            values['PER'] = per

        if values:
            self.add_data_point(t_ms, values)


class LatencyGraph(MetricsGraphWidget):
    """Graph showing latency for both directions (separate from jitter)."""

    def __init__(self, parent=None):
        super().__init__("Latency", parent)

        # Add series for latency
        self.add_series('L→R Latency', '#3498db')  # Blue
        self.add_series('R→L Latency', '#9b59b6')  # Purple

        # Set Y axis
        self.plot_widget.setYRange(0, 200)
        self.plot_widget.setLabel('left', 'Latency', units='ms')

    def update_metrics(self, metrics: dict):
        """Update graph with new metrics data."""
        if metrics.get('mode') != 'byte':
            return

        t_ms = metrics.get('t_ms', 0)
        # Latency can be derived from RTT/2 for symmetric channels
        rtt = metrics.get('rtt_ms', 0)
        if rtt > 0:
            latency = rtt / 2.0
            values = {
                'L→R Latency': latency,
                'R→L Latency': latency,
            }
            self.add_data_point(t_ms, values)


class SummaryStatsWidget(QWidget):
    """Widget showing summary statistics at the end of a simulation run."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._reset_accumulators()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("Summary Statistics")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Stats grid
        self.stats_frame = QFrame()
        self.stats_frame.setFrameStyle(QFrame.StyledPanel)
        stats_layout = QGridLayout(self.stats_frame)

        # Create labels for stats
        self.stat_labels = {}
        stats_config = [
            ('duration', 'Duration:', '0 ms'),
            ('mode', 'Mode:', '-'),
            ('avg_loss_l2r', 'Avg Loss L→R:', '0.000'),
            ('avg_loss_r2l', 'Avg Loss R→L:', '0.000'),
            ('avg_jitter_l2r', 'Avg Jitter L→R:', '0.0 ms'),
            ('avg_jitter_r2l', 'Avg Jitter R→L:', '0.0 ms'),
            ('avg_rtt', 'Avg RTT:', '0 ms'),
            ('total_goodput_l', 'Avg Goodput L→R:', '0 bps'),
            ('total_goodput_r', 'Avg Goodput R→L:', '0 bps'),
            ('avg_snr', 'Avg SNR:', '- dB'),
            ('avg_ber', 'Avg BER:', '-'),
            ('total_per', 'Frame Loss Rate:', '-'),
            ('total_bytes_l', 'Total Bytes L:', '0'),
            ('total_bytes_r', 'Total Bytes R:', '0'),
        ]

        for i, (key, label_text, default) in enumerate(stats_config):
            row = i // 2
            col = (i % 2) * 2

            label = QLabel(label_text)
            label.setFont(QFont("Arial", 9))
            value = QLabel(default)
            value.setFont(QFont("Arial", 9, QFont.Bold))
            value.setAlignment(Qt.AlignRight)

            stats_layout.addWidget(label, row, col)
            stats_layout.addWidget(value, row, col + 1)
            self.stat_labels[key] = value

        layout.addWidget(self.stats_frame)

    def _reset_accumulators(self):
        """Reset all metric accumulators."""
        self._samples = 0
        self._last_t_ms = 0
        self._mode = None

        # Byte mode accumulators
        self._sum_loss_l2r = 0.0
        self._sum_loss_r2l = 0.0
        self._sum_jitter_l2r = 0.0
        self._sum_jitter_r2l = 0.0
        self._sum_rtt = 0.0
        self._rtt_samples = 0
        self._sum_goodput_l = 0.0
        self._sum_goodput_r = 0.0
        self._goodput_samples = 0

        # Audio mode accumulators
        self._sum_snr = 0.0
        self._snr_samples = 0
        self._sum_ber = 0.0
        self._ber_samples = 0
        self._total_bytes = 0
        self._total_lost_bytes = 0
        self.total_bytes_l = 0
        self.total_bytes_r = 0

    def update_metrics(self, metrics: dict):
        """Accumulate metrics for summary."""
        self._samples += 1
        self._last_t_ms = metrics.get('t_ms', self._last_t_ms)
        self._mode = metrics.get('mode', self._mode)

        if metrics.get('mode') == 'byte':
            self._sum_loss_l2r += metrics.get('l2r_loss', 0)
            self._sum_loss_r2l += metrics.get('r2l_loss', 0)
            self._sum_jitter_l2r += metrics.get('l2r_jitter', 0)
            self._sum_jitter_r2l += metrics.get('r2l_jitter', 0)

            if metrics.get('rtt_ms', 0) > 0:
                self._sum_rtt += metrics.get('rtt_ms', 0)
                self._rtt_samples += 1

            if metrics.get('goodput_l_bps', 0) > 0:
                self._sum_goodput_l += metrics.get('goodput_l_bps', 0)
                self._sum_goodput_r += metrics.get('goodput_r_bps', 0)
                self._goodput_samples += 1

        elif metrics.get('mode') == 'audio':
            if metrics.get('snr_db') is not None:
                self._sum_snr += metrics.get('snr_db', 0)
                self._snr_samples += 1

            if metrics.get('ber') is not None:
                self._sum_ber += metrics.get('ber', 0)
                self._ber_samples += 1

            if metrics.get('total_bytes') is not None:
                self._total_bytes = metrics.get('total_bytes', 0)
                self._total_lost_bytes = metrics.get('total_lost_bytes', 0)
            
            # Track bytes processed
            if metrics.get('total_bytes_l') is not None:
                self.total_bytes_l = metrics.get('total_bytes_l', 0)
            if metrics.get('total_bytes_r') is not None:
                self.total_bytes_r = metrics.get('total_bytes_r', 0)

    def finalize(self):
        """Calculate and display final summary statistics."""
        # Duration
        self.stat_labels['duration'].setText(f"{self._last_t_ms} ms")
        self.stat_labels['mode'].setText(self._mode.upper() if self._mode else '-')

        if self._samples > 0:
            # Byte mode stats
            avg_loss_l2r = self._sum_loss_l2r / self._samples
            avg_loss_r2l = self._sum_loss_r2l / self._samples
            avg_jitter_l2r = self._sum_jitter_l2r / self._samples
            avg_jitter_r2l = self._sum_jitter_r2l / self._samples

            self.stat_labels['avg_loss_l2r'].setText(f"{avg_loss_l2r:.3f}")
            self.stat_labels['avg_loss_r2l'].setText(f"{avg_loss_r2l:.3f}")
            self.stat_labels['avg_jitter_l2r'].setText(f"{avg_jitter_l2r:.1f} ms")
            self.stat_labels['avg_jitter_r2l'].setText(f"{avg_jitter_r2l:.1f} ms")

        if self._rtt_samples > 0:
            avg_rtt = self._sum_rtt / self._rtt_samples
            self.stat_labels['avg_rtt'].setText(f"{avg_rtt:.0f} ms")

        if self._goodput_samples > 0:
            avg_goodput_l = self._sum_goodput_l / self._goodput_samples
            avg_goodput_r = self._sum_goodput_r / self._goodput_samples
            self.stat_labels['total_goodput_l'].setText(self._format_bps(avg_goodput_l))
            self.stat_labels['total_goodput_r'].setText(self._format_bps(avg_goodput_r))

        # Audio mode stats
        if self._snr_samples > 0:
            avg_snr = self._sum_snr / self._snr_samples
            self.stat_labels['avg_snr'].setText(f"{avg_snr:.1f} dB")

        if self._ber_samples > 0:
            avg_ber = self._sum_ber / self._ber_samples
            self.stat_labels['avg_ber'].setText(f"{avg_ber:.4f}")

        if self._total_bytes > 0:
            per = self._total_lost_bytes / self._total_bytes
            self.stat_labels['total_per'].setText(
                f"{per:.1%} ({self._total_lost_bytes}/{self._total_bytes})"
            )
        
        # Display bytes processed
        if self.total_bytes_l > 0:
            self.stat_labels['total_bytes_l'].setText(f"{self.total_bytes_l:,}")
        if self.total_bytes_r > 0:
            self.stat_labels['total_bytes_r'].setText(f"{self.total_bytes_r:,}")

    def _format_bps(self, bps: float) -> str:
        """Format bits per second in human-readable form."""
        if bps >= 1_000_000:
            return f"{bps/1_000_000:.2f} Mbps"
        elif bps >= 1_000:
            return f"{bps/1_000:.2f} kbps"
        else:
            return f"{bps:.0f} bps"

    def clear_data(self):
        """Reset all stats."""
        self._reset_accumulators()
        for key, label in self.stat_labels.items():
            if key == 'duration':
                label.setText('0 ms')
            elif key == 'mode':
                label.setText('-')
            elif 'loss' in key:
                label.setText('0.000')
            elif 'jitter' in key or 'rtt' in key:
                label.setText('0.0 ms')
            elif 'goodput' in key:
                label.setText('0 bps')
            elif 'total_bytes' in key:
                label.setText('0')
            else:
                label.setText('-')


class EnhancedCombinedMetricsGraph(QWidget):
    """Enhanced combined widget with all graphs for both modes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._current_mode = None

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Byte mode graphs
        self.network_graph = NetworkMetricsGraph("L→R")
        self.jitter_graph = JitterMetricsGraph()
        self.goodput_graph = GoodputGraph()
        self.rtt_graph = RTTGraph()

        # Audio mode graphs
        self.snr_graph = SNRGraph()
        self.ber_per_graph = BERPERGraph()

        # Summary stats (shown for both modes)
        self.summary_stats = SummaryStatsWidget()

        # Add byte mode graphs
        layout.addWidget(self.network_graph)
        layout.addWidget(self.jitter_graph)
        layout.addWidget(self.goodput_graph)
        layout.addWidget(self.rtt_graph)

        # Add audio mode graphs (hidden initially)
        layout.addWidget(self.snr_graph)
        layout.addWidget(self.ber_per_graph)

        # Summary always at bottom
        layout.addWidget(self.summary_stats)

        # Initially show byte mode
        self._show_byte_mode()

    def _show_byte_mode(self):
        """Show byte mode graphs, hide audio mode graphs."""
        self.network_graph.setVisible(True)
        self.jitter_graph.setVisible(True)
        self.goodput_graph.setVisible(True)
        self.rtt_graph.setVisible(True)
        self.snr_graph.setVisible(False)
        self.ber_per_graph.setVisible(False)

    def _show_audio_mode(self):
        """Show audio mode graphs, hide byte mode graphs."""
        self.network_graph.setVisible(False)
        self.jitter_graph.setVisible(False)
        self.goodput_graph.setVisible(False)
        self.rtt_graph.setVisible(False)
        self.snr_graph.setVisible(True)
        self.ber_per_graph.setVisible(True)

    def update_metrics(self, metrics: dict):
        """Route metrics to appropriate graphs."""
        mode = metrics.get('mode')

        # Switch graph visibility based on mode
        if mode != self._current_mode:
            self._current_mode = mode
            if mode == 'byte':
                self._show_byte_mode()
            elif mode == 'audio':
                self._show_audio_mode()

        # Update the appropriate graphs
        if mode == 'byte':
            self.network_graph.update_metrics(metrics)
            self.jitter_graph.update_metrics(metrics)
            self.goodput_graph.update_metrics(metrics)
            self.rtt_graph.update_metrics(metrics)
        elif mode == 'audio':
            self.snr_graph.update_metrics(metrics)
            self.ber_per_graph.update_metrics(metrics)

        # Always update summary stats
        self.summary_stats.update_metrics(metrics)

    def finalize(self):
        """Finalize summary statistics after simulation ends."""
        self.summary_stats.finalize()

    def clear_data(self):
        """Clear all graph data."""
        self.network_graph.clear_data()
        self.jitter_graph.clear_data()
        self.goodput_graph.clear_data()
        self.rtt_graph.clear_data()
        self.snr_graph.clear_data()
        self.ber_per_graph.clear_data()
        self.summary_stats.clear_data()
        self._current_mode = None
