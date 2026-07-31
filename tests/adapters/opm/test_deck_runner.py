from pathlib import Path, PureWindowsPath

import pytest

from petro_agent.adapters.opm.deck_runner import (
    FlowExecutionConfig,
    build_flow_command,
    inspect_flow_environment,
    run_flow,
    windows_path_to_wsl,
)


def test_missing_wsl_is_reported(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    result = inspect_flow_environment(FlowExecutionConfig())
    assert result.available is False
    assert "wsl.exe" in result.reason


def test_invalid_deck_is_rejected_before_flow_lookup(tmp_path: Path):
    with pytest.raises(ValueError, match="不是 .DATA"):
        run_flow(tmp_path / "missing.txt", tmp_path / "output")


def test_windows_path_to_wsl(monkeypatch):
    fake = PureWindowsPath("F:/Projects/petro-agent/model.DATA")
    monkeypatch.setattr("pathlib.Path.resolve", lambda self: fake)
    assert windows_path_to_wsl(fake) == "/mnt/f/Projects/petro-agent/model.DATA"


def test_build_wsl_command(monkeypatch):
    values = iter(
        [
            PureWindowsPath("F:/Projects/petro-agent/model.DATA"),
            PureWindowsPath("F:/Projects/petro-agent/outputs/opm"),
            PureWindowsPath("F:/Projects/petro-agent/model.DATA"),
            PureWindowsPath("F:/Projects/petro-agent/outputs/opm"),
        ]
    )
    monkeypatch.setattr("pathlib.Path.resolve", lambda self: next(values))
    command = build_flow_command("model.DATA", "outputs/opm", FlowExecutionConfig())
    assert command[:6] == [
        "wsl.exe",
        "-d",
        "Ubuntu-24.04",
        "--",
        "flow",
        "/mnt/f/Projects/petro-agent/model.DATA",
    ]
    assert "--output-dir=/mnt/f/Projects/petro-agent/outputs/opm" in command
    assert "--enable-esmry=true" in command
