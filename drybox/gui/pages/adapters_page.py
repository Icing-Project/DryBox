from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QDoubleSpinBox, QCheckBox, QSpinBox, QSizePolicy
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # drybox/ui -> drybox -> projectroot
ADAPTERS_DIR = PROJECT_ROOT / "adapters"


class AdaptersPage(QWidget):
    def __init__(self, adapters_dir: Path | None = None):
        super().__init__()
        if adapters_dir is None:
            adapters_dir = ADAPTERS_DIR
        self.adapters_dir = adapters_dir
        self.adapters = self._find_adapters()

        layout = QHBoxLayout(self)

        # Left Adapter
        self.left_box, self.left_adapter_combo, self.left_gain, self.left_modem_widgets = \
            self._create_adapter_box("Left Adapter")
        layout.addWidget(self.left_box)

        # Right Adapter
        self.right_box, self.right_adapter_combo, self.right_gain, self.right_modem_widgets = \
            self._create_adapter_box("Right Adapter")
        layout.addWidget(self.right_box)

    def _find_adapters(self) -> list[str]:
        if not self.adapters_dir.exists():
            return []
        return [f.name for f in self.adapters_dir.glob("*.py")]

    def _create_adapter_box(self, title: str):
        """Build a QGroupBox with Adapter dropdown, Gain, and inline Modem box."""
        box = QGroupBox(title)
        v_layout = QVBoxLayout(box)

        # --- Adapter & Gain ---
        form = QFormLayout()
        combo = QComboBox()
        combo.addItems(self.adapters)
        if "nade_adapter.py" in self.adapters:
            combo.setCurrentText("nade_adapter.py")
        form.addRow("Adapter:", combo)

        gain = QDoubleSpinBox()
        gain.setRange(0.0, 10.0)
        gain.setSingleStep(0.1)
        gain.setDecimals(2)
        gain.setValue(1.00)
        form.addRow("Gain:", gain)

        v_layout.addLayout(form)

        # --- Modem box directly under Gain ---
        modem_box = QGroupBox("Modem")
        modem_layout = QFormLayout(modem_box)

        vocoder_combo = QComboBox()
        vocoder_combo.addItems(["none", "amr12k2_mock", "evs13k2_mock", "opus_nb_mock"])
        modem_layout.addRow("Vocoder:", vocoder_combo)

        vad_checkbox = QCheckBox("Enable VAD/DTX")
        modem_layout.addRow("", vad_checkbox)

        channel_combo = QComboBox()
        channel_combo.addItems(["none", "awgn", "fading"])
        modem_layout.addRow("Channel:", channel_combo)

        snr_spin = QSpinBox()
        snr_spin.setRange(0, 50)
        snr_spin.setSingleStep(1)
        snr_spin.setValue(20)
        modem_layout.addRow("SNR (dB):", snr_spin)

        doppler_spin = QSpinBox()
        doppler_spin.setRange(0, 10000)
        doppler_spin.setSingleStep(1)
        doppler_spin.setValue(50)
        modem_layout.addRow("Max Doppler freq (Hz):", doppler_spin)

        num_paths_spin = QSpinBox()
        num_paths_spin.setRange(1, 100)
        num_paths_spin.setSingleStep(1)
        num_paths_spin.setValue(8)
        modem_layout.addRow("Multipath components:", num_paths_spin)

        modem_box.setLayout(modem_layout)

        # Add Modem box **directly under Gain**
        v_layout.addWidget(modem_box)

        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        modem_widgets = {
            "vocoder": vocoder_combo,
            "vad_dtx": vad_checkbox,
            "channel_type": channel_combo,
            "snr_db": snr_spin,
            "doppler_hz": doppler_spin,
            "num_paths": num_paths_spin
        }

        return box, combo, gain, modem_widgets

    # === Scenario support ===
    def set_from_scenario(self, left: dict, right: dict):
        # Left
        self.left_adapter_combo.setCurrentText(left.get("adapter", "nade_adapter.py"))
        self.left_gain.setValue(float(left.get("gain", 1.0)))
        modem_left = left.get("modem", {})
        for k, w in self.left_modem_widgets.items():
            if k in modem_left:
                if isinstance(w, QCheckBox):
                    w.setChecked(modem_left[k])
                else:
                    w.setValue(modem_left[k]) if hasattr(w, "setValue") else w.setCurrentText(modem_left[k])

        # Right
        self.right_adapter_combo.setCurrentText(right.get("adapter", "nade_adapter.py"))
        self.right_gain.setValue(float(right.get("gain", 1.0)))
        modem_right = right.get("modem", {})
        for k, w in self.right_modem_widgets.items():
            if k in modem_right:
                if isinstance(w, QCheckBox):
                    w.setChecked(modem_right[k])
                else:
                    w.setValue(modem_right[k]) if hasattr(w, "setValue") else w.setCurrentText(modem_right[k])

    def to_dict(self):
        left = {
            "adapter": self.left_adapter_combo.currentText(),
            "gain": round(self.left_gain.value(), 3),
            "modem": {
                k: (w.isChecked() if isinstance(w, QCheckBox)
                    else (round(w.value(), 3) if isinstance(w, QDoubleSpinBox) else (
                        w.value() if hasattr(w, "value") else w.currentText())))
                for k, w in self.left_modem_widgets.items()
            }
        }
        right = {
            "adapter": self.right_adapter_combo.currentText(),
            "gain": round(self.right_gain.value(), 3),
            "modem": {
                k: (w.isChecked() if isinstance(w, QCheckBox)
                    else (round(w.value(), 3) if isinstance(w, QDoubleSpinBox) else (
                        w.value() if hasattr(w, "value") else w.currentText())))
                for k, w in self.right_modem_widgets.items()
            }
        }
        return left, right
