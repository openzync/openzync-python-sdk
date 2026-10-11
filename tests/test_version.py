"""Tests for the version module."""

from __future__ import annotations

import pytest


class TestVersion:
    """Tests for ``_version``."""

    def test_version_is_string(self):
        """__version__ is always a string."""
        from openzync._version import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_fallback_on_import_error(self, monkeypatch):
        """RuntimeError (not a silent '0.0.0') when package metadata is missing."""
        import importlib
        from importlib.metadata import PackageNotFoundError

        import openzync._version as vz

        def broken_version(pkg: str) -> str:
            raise PackageNotFoundError(pkg)

        monkeypatch.setattr(
            "importlib.metadata.version",
            broken_version,
        )

        with pytest.raises(RuntimeError, match="metadata not found"):
            importlib.reload(vz)

        # Restore the real module state (monkeypatch auto-restores after test)
        monkeypatch.undo()
        importlib.reload(vz)
