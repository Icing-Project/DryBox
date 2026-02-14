import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from drybox.gui.pages.main_window import MainWindow


class DummySignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, value):
        for callback in list(self._callbacks):
            callback(value)


class DummyThread:
    def __init__(self):
        self.finished_signal = DummySignal()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _stub_successful_run(window: MainWindow) -> DummyThread:
    thread = DummyThread()

    def _run_scenario():
        window.runner_page.runner_thread = thread
        return True

    window.runner_page.run_scenario = _run_scenario
    return thread


def test_run_button_supports_single_click_rerun(qapp):
    window = MainWindow()
    first_thread = _stub_successful_run(window)

    window.on_run_clicked()
    assert not window.btn_run.isEnabled()
    assert window.btn_stop.isEnabled()

    first_thread.finished_signal.emit(0)
    assert window.btn_run.isEnabled()
    assert not window.btn_stop.isEnabled()

    _stub_successful_run(window)
    window.on_run_clicked()
    assert not window.btn_run.isEnabled()
    assert window.btn_stop.isEnabled()

    window.close()


def test_failed_run_start_keeps_controls_idle(qapp):
    window = MainWindow()

    def _run_scenario():
        window.runner_page.runner_thread = None
        return False

    window.runner_page.run_scenario = _run_scenario
    window.on_run_clicked()

    assert window.btn_run.isEnabled()
    assert not window.btn_stop.isEnabled()

    window.close()


def test_stop_click_restores_idle_controls(qapp):
    window = MainWindow()
    _stub_successful_run(window)

    called = {"stop": False}

    def _stop_scenario():
        called["stop"] = True

    window.runner_page.stop_scenario = _stop_scenario

    window.on_run_clicked()
    assert not window.btn_run.isEnabled()
    assert window.btn_stop.isEnabled()

    window.on_stop_clicked()
    assert called["stop"] is True
    assert window.btn_run.isEnabled()
    assert not window.btn_stop.isEnabled()

    window.close()
