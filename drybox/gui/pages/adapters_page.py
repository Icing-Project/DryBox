from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QDoubleSpinBox, QCheckBox, QSpinBox, QSizePolicy
)

from drybox.core.adapter_registry import (
    AdapterInfo,
    discover_adapters,
    resolve_identifier,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ADAPTERS_DIR = PROJECT_ROOT / "adapters"
DEFAULT_IDENTIFIER = "nade-python"


class AdaptersPage(QWidget):
    def __init__(self, adapters_dir: Optional[Path] = None):
        super().__init__()
        self.adapters_dir = (adapters_dir or ADAPTERS_DIR).resolve()
        self.adapter_infos = discover_adapters(self.adapters_dir)
        self._adapter_index: Dict[str, AdapterInfo] = {
            info.identifier: info for info in self.adapter_infos
        }

        layout = QHBoxLayout(self)

        self.left_box, self.left_adapter_combo, self.left_gain, self.left_modem_widgets = \
            self._create_adapter_box("Left Adapter")
        layout.addWidget(self.left_box)

        self.right_box, self.right_adapter_combo, self.right_gain, self.right_modem_widgets = \
            self._create_adapter_box("Right Adapter")
        layout.addWidget(self.right_box)

        self._refresh_combo_items()

    # === Discovery helpers ===
    def _refresh_combo_items(self) -> None:
        """Populate both combo boxes with the currently known adapters."""
        for combo in (self.left_adapter_combo, self.right_adapter_combo):
            selected_id = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for info in self.adapter_infos:
                combo.addItem(info.display_name, info.identifier)
            combo.blockSignals(False)
            self._set_combo_to_identifier(combo, selected_id or DEFAULT_IDENTIFIER)

    def _ensure_adapter_identifier(self, identifier: str) -> AdapterInfo:
        if not identifier:
            identifier = DEFAULT_IDENTIFIER
        info = self._adapter_index.get(identifier)
        if info is not None:
            return info

        resolved = resolve_identifier(identifier, self.adapters_dir)
        if resolved is None:
            source = "file" if identifier.endswith(".py") else "entrypoint"
            resolved = AdapterInfo(
                identifier=identifier,
                display_name=f"{identifier} (missing)",
                spec=identifier,
                source=source,
                metadata={"missing": "true"},
            )
        self.adapter_infos.append(resolved)
        self.adapter_infos.sort(key=lambda info: (0 if info.source == "file" else 1, info.display_name.lower()))
        self._adapter_index[identifier] = resolved
        self._refresh_combo_items()
        return resolved

    def _info_for_identifier(self, identifier: Optional[str]) -> AdapterInfo:
        if identifier is None:
            return self._ensure_adapter_identifier(DEFAULT_IDENTIFIER)
        return self._ensure_adapter_identifier(identifier)

    def _set_combo_to_identifier(self, combo: QComboBox, identifier: str) -> None:
        idx = combo.findData(identifier)
        if idx == -1 and combo.count() > 0:
            idx = 0
        if idx >= 0:
            combo.setCurrentIndex(idx)

    # === UI builders ===
    def _create_adapter_box(self, title: str):
        box = QGroupBox(title)
        v_layout = QVBoxLayout(box)

        form = QFormLayout()
        combo = QComboBox()
        form.addRow("Adapter:", combo)

        gain = QDoubleSpinBox()
        gain.setRange(0.0, 10.0)
        gain.setSingleStep(0.1)
        gain.setDecimals(2)
        gain.setValue(1.00)
        form.addRow("Gain:", gain)

        v_layout.addLayout(form)

        modem_box = QGroupBox("Modem")
        modem_layout = QFormLayout(modem_box)

        vocoder_combo = QComboBox()
        vocoder_combo.addItems(["amr12k2_mock", "evs13k2_mock", "opus_nb_mock"])
        modem_layout.addRow("Vocoder:", vocoder_combo)

        vad_checkbox = QCheckBox("Enable VAD/DTX")
        modem_layout.addRow("", vad_checkbox)

        channel_combo = QComboBox()
        channel_combo.addItems(["awgn", "fading"])
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
        v_layout.addWidget(modem_box)
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        modem_widgets = {
            "vocoder": vocoder_combo,
            "vad_dtx": vad_checkbox,
            "channel_type": channel_combo,
            "snr_db": snr_spin,
            "doppler_hz": doppler_spin,
            "num_paths": num_paths_spin,
        }

        return box, combo, gain, modem_widgets

    # === Scenario support ===
    def set_from_scenario(self, left: dict, right: dict):
        left_id = left.get("adapter", DEFAULT_IDENTIFIER)
        right_id = right.get("adapter", DEFAULT_IDENTIFIER)

        self._ensure_adapter_identifier(left_id)
        self._ensure_adapter_identifier(right_id)

        self._set_combo_to_identifier(self.left_adapter_combo, left_id)
        self._set_combo_to_identifier(self.right_adapter_combo, right_id)

        self.left_gain.setValue(float(left.get("gain", 1.0)))
        self.right_gain.setValue(float(right.get("gain", 1.0)))

        for widgets, config in ((self.left_modem_widgets, left.get("modem", {})),
                                (self.right_modem_widgets, right.get("modem", {}))):
            for key, widget in widgets.items():
                if key not in config:
                    continue
                value = config[key]
                if isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif hasattr(widget, "setValue"):
                    widget.setValue(value)  # type: ignore[arg-type]
                else:
                    widget.setCurrentText(value)

    def to_dict(self) -> Tuple[dict, dict]:
        left_adapter_id = self.left_adapter_combo.currentData()
        right_adapter_id = self.right_adapter_combo.currentData()

        def serialize(combo_id, gain_widget, modem_widgets):
            adapter_info = self._info_for_identifier(combo_id)
            return {
                "adapter": adapter_info.identifier,
                "gain": round(gain_widget.value(), 3),
                "modem": {
                    key: (
                        widget.isChecked() if isinstance(widget, QCheckBox)
                        else (round(widget.value(), 3) if isinstance(widget, QDoubleSpinBox)
                              else (widget.value() if hasattr(widget, "value") else widget.currentText()))
                    )
                    for key, widget in modem_widgets.items()
                },
            }

        left = serialize(left_adapter_id, self.left_gain, self.left_modem_widgets)
        right = serialize(right_adapter_id, self.right_gain, self.right_modem_widgets)
        return left, right

    # === Runner integration ===
    def get_selected_adapter_infos(self) -> Tuple[AdapterInfo, AdapterInfo]:
        left_id = self.left_adapter_combo.currentData()
        right_id = self.right_adapter_combo.currentData()
        return self._info_for_identifier(left_id), self._info_for_identifier(right_id)

