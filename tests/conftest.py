"""Pytest fixtures for WallpaperDIY tests."""
import sys
import os
import tempfile
import shutil

import pytest

# Ensure platforms/desktop is on path (main.py lives there)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_desktop = os.path.join(_root, "platforms", "desktop")
sys.path.insert(0, _desktop)


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for PyQt tests (session-scoped)."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def temp_output_dir(monkeypatch):
    """Use a temporary directory for output instead of project output/."""
    tmp = tempfile.mkdtemp()
    try:
        # Patch get_output_dir to return our temp dir
        import main as main_mod
        original_get_output_dir = main_mod.get_output_dir

        def patched_get_output_dir():
            return tmp

        monkeypatch.setattr(main_mod, "get_output_dir", patched_get_output_dir)
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def wallpaper_app(qapp):
    """Create WallpaperUltra instance for testing (requires qapp)."""
    from main import WallpaperUltra
    win = WallpaperUltra()
    yield win
