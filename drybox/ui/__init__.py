# UI module for DryBox

# Import Qt components only when needed to avoid import errors
def get_main_window():
    from .main_window import MainWindow
    return MainWindow

def get_scenario_widget():
    from .scenario_widget import ScenarioWidget
    return ScenarioWidget

__all__ = ['get_main_window', 'get_scenario_widget']