from pathlib import Path
import yaml
from typing import Tuple

from drybox.core.paths import SCENARIOS_DIR

# === Scenario helpers ===

def collect_scenario(general_page, adapters_page) -> dict:
    """Build a scenario dict from GUI pages"""
    scenario = {}
    scenario.update(general_page.to_dict())
    scenario["left"], scenario["right"] = adapters_page.to_dict()
    return scenario

def apply_scenario(general_page, adapters_page, scenario: dict):
    """Apply a scenario dict to GUI pages"""
    general_page.set_from_scenario(scenario)
    adapters_page.set_from_scenario(scenario.get("left", {}), scenario.get("right", {}))

# === Scenario file I/O ===

def load_scenario_file(path: Path) -> dict:
    """Load a YAML scenario file"""
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def save_scenario_file(path: Path, scenario: dict):
    """Save a YAML scenario file"""
    with open(path, "w") as f:
        yaml.safe_dump(scenario, f, sort_keys=False)

# === Scenario path helpers ===

def default_scenario_path(name: str = "new_scenario.yaml") -> Path:
    """Return default scenario path"""
    return SCENARIOS_DIR / name

def ensure_yaml_suffix(path: Path) -> Path:
    """Ensure file path ends with .yaml"""
    if path.suffix not in (".yaml", ".yml"):
        path = path.with_suffix(".yaml")
    return path
