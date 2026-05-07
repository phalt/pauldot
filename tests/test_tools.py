"""Tests for tools.py — tool check, install, update, and reconcile logic."""

import subprocess
import unittest.mock

from pauldot import config, tools


def _tool(
    name: str,
    check: str,
    macos: str | None = None,
    linux: str | None = None,
    update_macos: str | None = None,
    update_linux: str | None = None,
) -> config.ToolDefinition:
    return config.ToolDefinition(
        name=name,
        check=check,
        install=config.ToolInstall(macos=macos, linux=linux),
        update=config.ToolUpdate(macos=update_macos, linux=update_linux),
    )


def test_check_present():
    """A tool whose check exits 0 is considered installed."""
    assert tools.check(_tool("t", check="true")) is True


def test_check_absent():
    """A tool whose check exits non-zero is considered not installed."""
    assert tools.check(_tool("t", check="false")) is False


def test_install_already_installed():
    result = tools.install(_tool("t", check="true", linux="true"), "linux")
    assert result.action == "already_installed"
    assert result.error is None


def test_install_missing_installs_successfully():
    result = tools.install(_tool("t", check="false", linux="true"), "linux")
    assert result.action == "installed"
    assert result.error is None


def test_install_skipped_no_os_entry():
    """Tool with no linux install entry is silently skipped on linux."""
    result = tools.install(_tool("t", check="false", macos="brew install t"), "linux")
    assert result.action == "skipped"
    assert result.error is None


def test_install_failed_records_error():
    result = tools.install(_tool("t", check="false", linux="false"), "linux")
    assert result.action == "failed"
    assert result.error is not None


def test_install_does_not_use_capture_output():
    """install() must not pass capture_output — output streams to the terminal."""
    with unittest.mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = unittest.mock.Mock(spec=subprocess.CompletedProcess, returncode=0)
        mock_run.side_effect = [
            unittest.mock.Mock(spec=subprocess.CompletedProcess, returncode=1),  # check fails
            unittest.mock.Mock(spec=subprocess.CompletedProcess, returncode=0),  # install succeeds
        ]
        tools.install(_tool("t", check="false", linux="true"), "linux")
        install_call = mock_run.call_args_list[1]
        assert "capture_output" not in install_call.kwargs or install_call.kwargs["capture_output"] is False


def test_install_no_output_field():
    """ToolResult has no output field after removing verbose mode."""
    result = tools.install(_tool("t", check="true"), "linux")
    assert not hasattr(result, "output")


def test_reconcile_processes_all():
    all_tools = {
        "present": _tool("present", check="true", linux="true"),
        "absent": _tool("absent", check="false", linux="true"),
    }
    results = tools.reconcile(["present", "absent"], all_tools, "linux")
    assert len(results) == 2
    assert results[0].action == "already_installed"
    assert results[1].action == "installed"


def test_reconcile_continues_after_failure():
    """A failed install does not abort the reconcile loop."""
    all_tools = {
        "fails": _tool("fails", check="false", linux="false"),
        "present": _tool("present", check="true"),
    }
    results = tools.reconcile(["fails", "present"], all_tools, "linux")
    assert len(results) == 2
    assert results[0].action == "failed"
    assert results[1].action == "already_installed"


def test_reconcile_undefined_tool_is_failed():
    results = tools.reconcile(["undefined"], {}, "linux")
    assert results[0].action == "failed"
    assert "not defined" in (results[0].error or "")


def test_reconcile_empty_profile():
    results = tools.reconcile([], {}, "linux")
    assert results == []


# — update() ——————————————————————————————————————————————————————————————————


def test_update_installed_with_command():
    result = tools.update(_tool("t", check="true", update_linux="true"), "linux")
    assert result.action == "updated"
    assert result.error is None


def test_update_not_installed():
    """update() on a missing tool returns not_installed without running the update command."""
    result = tools.update(_tool("t", check="false", update_linux="true"), "linux")
    assert result.action == "not_installed"


def test_update_no_update_command():
    """Tool without an update command for the current OS is skipped."""
    result = tools.update(_tool("t", check="true", update_macos="brew upgrade t"), "linux")
    assert result.action == "skipped"


def test_update_failed():
    result = tools.update(_tool("t", check="true", update_linux="false"), "linux")
    assert result.action == "failed"
    assert result.error is not None


def test_update_does_not_use_capture_output():
    """update() must not pass capture_output — output streams to the terminal."""
    with unittest.mock.patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            unittest.mock.Mock(spec=subprocess.CompletedProcess, returncode=0),  # check passes
            unittest.mock.Mock(spec=subprocess.CompletedProcess, returncode=0),  # update succeeds
        ]
        tools.update(_tool("t", check="true", update_linux="true"), "linux")
        update_call = mock_run.call_args_list[1]
        assert "capture_output" not in update_call.kwargs or update_call.kwargs["capture_output"] is False
