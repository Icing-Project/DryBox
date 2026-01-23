import random
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, QPushButton, QRadioButton, QButtonGroup
)


class GeneralPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        left_column = QVBoxLayout()
        right_column = QVBoxLayout()

        # --- Basic box ---
        basic_box = QGroupBox("Basic")
        basic_layout = QFormLayout(basic_box)

        # Mode
        self.mode_group = QButtonGroup(self)
        self.mode_byte = QRadioButton("ByteLink (ModeA)")
        self.mode_audio = QRadioButton("AudioBlock (ModeB)")
        self.mode_group.addButton(self.mode_byte)
        self.mode_group.addButton(self.mode_audio)
        self.mode_audio.setChecked(True)
        mode_widget = QWidget()
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0,0,0,0)
        mode_layout.addWidget(self.mode_byte)
        mode_layout.addWidget(self.mode_audio)
        basic_layout.addRow("Mode:", mode_widget)

        # Duration
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 50000)
        self.duration_spin.setSingleStep(100)
        self.duration_spin.setValue(2000)
        basic_layout.addRow("Duration (ms):", self.duration_spin)

        # Seed
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(random.randint(0, 999999))
        seed_widget = QWidget()
        seed_layout = QHBoxLayout(seed_widget)
        seed_layout.setContentsMargins(0, 0, 0, 0)
        seed_layout.addWidget(self.seed_spin)
        self.seed_button = QPushButton("Random")
        seed_layout.addWidget(self.seed_button)
        basic_layout.addRow("Seed:", seed_widget)
        self.seed_button.clicked.connect(lambda: self.seed_spin.setValue(random.randint(0, 999999)))

        # --- Network box ---
        network_box = QGroupBox("Network")
        network_layout = QFormLayout(network_box)

        self.bearer_combo = QComboBox()
        self.bearer_combo.addItems(["volte_evs", "cs_gsm", "pstn_g711", "ott_udp"])
        network_layout.addRow("Bearer:", self.bearer_combo)

        self.loss_spin = QDoubleSpinBox()
        self.loss_spin.setRange(0.0, 1.0)
        self.loss_spin.setSingleStep(0.01)
        self.loss_spin.setDecimals(3)
        self.loss_spin.setValue(0.0)
        network_layout.addRow("Loss rate:", self.loss_spin)

        # Advanced network options
        self.latency_spin = QSpinBox()
        self.latency_spin.setRange(0, 1000)
        self.latency_spin.setValue(20)
        network_layout.addRow("Latency (ms):", self.latency_spin)

        self.jitter_spin = QSpinBox()
        self.jitter_spin.setRange(0, 500)
        self.jitter_spin.setValue(5)
        network_layout.addRow("Jitter (ms):", self.jitter_spin)

        self.reorder_spin = QDoubleSpinBox()
        self.reorder_spin.setRange(0.0, 1.0)
        self.reorder_spin.setSingleStep(0.01)
        self.reorder_spin.setDecimals(3)
        self.reorder_spin.setValue(0.0)
        network_layout.addRow("Reorder rate:", self.reorder_spin)

        self.ge_good_bad_spin = QDoubleSpinBox()
        self.ge_good_bad_spin.setRange(0.0, 1.0)
        self.ge_good_bad_spin.setSingleStep(0.001)
        self.ge_good_bad_spin.setDecimals(4)
        self.ge_good_bad_spin.setValue(0.001)
        network_layout.addRow("SAR P good→bad:", self.ge_good_bad_spin)

        self.ge_bad_good_spin = QDoubleSpinBox()
        self.ge_bad_good_spin.setRange(0.0, 1.0)
        self.ge_bad_good_spin.setSingleStep(0.001)
        self.ge_bad_good_spin.setDecimals(4)
        self.ge_bad_good_spin.setValue(0.1)
        network_layout.addRow("SAR P bad→good:", self.ge_bad_good_spin)

        self.mtu_spin = QSpinBox()
        self.mtu_spin.setRange(16, 10000)
        self.mtu_spin.setValue(1500)
        network_layout.addRow("MTU bytes:", self.mtu_spin)

        # --- Other box ---
        other_box = QGroupBox("Other")
        other_layout = QFormLayout(other_box)
        
         # --- Another box ---
        another_box = QGroupBox("Another")
        another_layout = QFormLayout(another_box)

        # --- Layout ---
        left_column.addWidget(basic_box)
        left_column.addWidget(other_box)
        right_column.addWidget(network_box)
        right_column.addWidget(another_box)

        layout.addLayout(left_column)
        layout.addLayout(right_column)

    # === Scenario support ===
    def set_from_scenario(self, scenario: dict):
        mode = scenario.get("mode", "audio")
        self.mode_byte.setChecked(mode.lower().startswith("byte"))
        self.mode_audio.setChecked(not mode.lower().startswith("byte"))
        self.duration_spin.setValue(scenario.get("duration_ms", 1000))
        self.seed_spin.setValue(scenario.get("seed", random.randint(0, 999999)))

        network = scenario.get("network", {})
        self.bearer_combo.setCurrentText(network.get("bearer", "volte_evs"))
        self.loss_spin.setValue(network.get("loss_rate", 0.0))
        self.latency_spin.setValue(network.get("latency_ms", 20))
        self.jitter_spin.setValue(network.get("jitter_ms", 5))
        self.reorder_spin.setValue(network.get("reorder_rate", 0.0))
        self.ge_good_bad_spin.setValue(network.get("ge_p_good_bad", 0.001))
        self.ge_bad_good_spin.setValue(network.get("ge_p_bad_good", 0.1))
        self.mtu_spin.setValue(network.get("mtu_bytes", 1500))

    def to_dict(self):
        mode = "byte" if self.mode_byte.isChecked() else "audio"
        return {
            "mode": mode,
            "duration_ms": self.duration_spin.value(),
            "seed": self.seed_spin.value(),
            "network": {
                "bearer": self.bearer_combo.currentText(),
                "loss_rate": round(self.loss_spin.value(), 3),
                "latency_ms": self.latency_spin.value(),
                "jitter_ms": self.jitter_spin.value(),
                "reorder_rate": round(self.reorder_spin.value(), 3),
                "ge_p_good_bad": round(self.ge_good_bad_spin.value(), 4),
                "ge_p_bad_good": round(self.ge_bad_good_spin.value(), 4),
                "mtu_bytes": self.mtu_spin.value()
            }
        }
