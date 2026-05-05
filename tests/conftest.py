"""Shared fixtures. fake_home must be used for any test that touches the filesystem."""

import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect HOME to a temp directory so apply never touches the real home."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home
