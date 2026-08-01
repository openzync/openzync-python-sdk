"""Tests for the version module."""

from __future__ import annotations


class TestVersion:
    """Tests for ``_version``."""

    def test_version_is_string(self):
        """__version__ is always a string."""
        from openzync._version import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_fallback_on_import_error(self, monkeypatch):
        """Fallback to 0.0.0 when importlib.metadata fails."""
        import openzync._version as vz

        # Simulate importlib.metadata.version raising an error
        def broken_version(pkg: str) -> str:
            raise ModuleNotFoundError(f"No module named {pkg}")

        monkeypatch.setattr(
            "importlib.metadata.version",
            broken_version,
        )

        # Re-execute the try/except block
        import importlib
        importlib.reload(vz)

        assert vz.__version__ == "0.0.0"

        # Restore by reloading again (monkeypatch auto-restores after test)
        importlib.reload(vz)
