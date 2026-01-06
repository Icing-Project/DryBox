from __future__ import annotations

import types
from pathlib import Path

import pytest

from drybox.core import adapter_registry


class FakeEntryPoint:
    def __init__(self, name: str, obj: type | object):
        self.name = name
        self._obj = obj
        self.value = "pkg.module:Adapter"
        self.module = "pkg.module"
        self.dist = types.SimpleNamespace(metadata={"Name": "fake-dist"})

    def load(self):
        return self._obj


def test_load_adapter_class_from_entrypoint(monkeypatch):
    class DummyAdapter:
        pass

    def fake_iter(group: str):
        assert group == adapter_registry.ENTRYPOINT_GROUP
        return [FakeEntryPoint("nade-python", DummyAdapter)]

    monkeypatch.setattr(adapter_registry, "_iter_entry_points", fake_iter)

    cls_from_entrypoint = adapter_registry.load_adapter_class("entrypoint:nade-python")
    assert cls_from_entrypoint is DummyAdapter

    cls_from_alias = adapter_registry.load_adapter_class("pkg:nade-python")
    assert cls_from_alias is DummyAdapter


def test_load_adapter_class_from_local_file(tmp_path: Path, monkeypatch):
    adapters_dir = tmp_path / "adapters"
    adapters_dir.mkdir()
    adapter_file = adapters_dir / "fake_adapter.py"
    adapter_file.write_text("""
class Adapter:
    pass
""", encoding="utf-8")

    monkeypatch.setattr(adapter_registry, "DEFAULT_ADAPTERS_DIR", adapters_dir)

    cls = adapter_registry.load_adapter_class("fake_adapter.py")
    assert cls.__name__ == "Adapter"


def test_discover_adapters_merges_sources(tmp_path: Path, monkeypatch):
    adapters_dir = tmp_path / "adapters"
    adapters_dir.mkdir()
    (adapters_dir / "local_a.py").write_text("class Adapter:\n    pass\n", encoding="utf-8")

    def fake_iter(group: str):
        return [FakeEntryPoint("nade-python", object())]

    monkeypatch.setattr(adapter_registry, "DEFAULT_ADAPTERS_DIR", adapters_dir)
    monkeypatch.setattr(adapter_registry, "_iter_entry_points", fake_iter)

    infos = adapter_registry.discover_adapters(adapters_dir)
    identifiers = [info.identifier for info in infos]

    assert "local_a.py" in identifiers
    assert "entrypoint:nade-python" in identifiers
    # Local files should appear before entry points
    assert identifiers.index("local_a.py") < identifiers.index("entrypoint:nade-python")


def test_resolve_identifier_fallback(tmp_path: Path, monkeypatch):
    adapters_dir = tmp_path / "adapters"
    adapters_dir.mkdir()
    (adapters_dir / "another.py").write_text("class Adapter:\n    pass\n", encoding="utf-8")

    monkeypatch.setattr(adapter_registry, "DEFAULT_ADAPTERS_DIR", adapters_dir)
    # Empty entry point list so resolution uses fallbacks
    monkeypatch.setattr(adapter_registry, "_iter_entry_points", lambda group: [])

    info_local = adapter_registry.resolve_identifier("another.py", adapters_dir)
    assert info_local is not None
    assert info_local.spec.endswith("another.py")

    info_entry = adapter_registry.resolve_identifier("entrypoint:nade-python", adapters_dir)
    assert info_entry is not None
    assert info_entry.spec == "entrypoint:nade-python"
    assert info_entry.identifier == "entrypoint:nade-python"

