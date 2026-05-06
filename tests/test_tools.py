"""Tests for tools.py — tool check, install, and reconcile logic."""

from pauldot import config, tools


def _tool(name: str, check: str, macos: str | None = None, linux: str | None = None) -> config.ToolDefinition:
    return config.ToolDefinition(
        name=name,
        check=check,
        install=config.ToolInstall(macos=macos, linux=linux),
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


# — verbose output ————————————————————————————————————————————————————————————


def test_install_verbose_captures_output_on_success():
    """verbose=True populates result.output for a successful install."""
    result = tools.install(_tool("t", check="false", linux="echo hello"), "linux", verbose=True)
    assert result.action == "installed"
    assert result.output is not None
    assert "hello" in result.output


def test_install_verbose_captures_output_on_failure():
    """verbose=True populates result.output even when install fails."""
    result = tools.install(_tool("t", check="false", linux="echo oops && false"), "linux", verbose=True)
    assert result.action == "failed"
    assert result.output is not None
    assert "oops" in result.output


def test_install_not_verbose_no_output():
    """Without verbose, result.output is None."""
    result = tools.install(_tool("t", check="false", linux="echo hello"), "linux", verbose=False)
    assert result.output is None


def test_install_already_installed_no_output():
    """Already-installed tools never populate output regardless of verbose."""
    result = tools.install(_tool("t", check="true", linux="echo hello"), "linux", verbose=True)
    assert result.action == "already_installed"
    assert result.output is None


def test_reconcile_verbose_passed_through():
    """verbose flag is threaded through reconcile to each install call."""
    all_tools = {"t": _tool("t", check="false", linux="echo hi")}
    results = tools.reconcile(["t"], all_tools, "linux", verbose=True)
    assert results[0].output is not None
    assert "hi" in results[0].output
