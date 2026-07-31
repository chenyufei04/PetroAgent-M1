from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FlowExecutionConfig:
    execution_mode: str = "wsl"
    wsl_distribution: str = "Ubuntu-24.04"
    flow_command: str = "flow"
    timeout_seconds: int = 1800

    @classmethod
    def from_environment(cls) -> "FlowExecutionConfig":
        return cls(
            # Windows 默认通过 wsl.exe 调用 Flow；
            # WSL/Linux 默认直接调用当前环境中的 Flow。
            execution_mode=os.getenv(
                "OPM_EXECUTION_MODE",
                "wsl" if os.name == "nt" else "native",
            )
            .strip()
            .lower(),
            wsl_distribution=os.getenv(
                "OPM_WSL_DISTRIBUTION",
                "Ubuntu-24.04",
            ).strip(),
            flow_command=os.getenv(
                "OPM_FLOW_COMMAND",
                "flow",
            ).strip(),
            timeout_seconds=int(
                os.getenv("OPM_FLOW_TIMEOUT_SECONDS", "1800")
            ),
        )


@dataclass(frozen=True)
class FlowEnvironment:
    execution_mode: str
    distribution: str | None
    executable: str | None
    available: bool
    version: str | None
    reason: str | None


@dataclass(frozen=True)
class FlowRunResult:
    command: list[str]
    return_code: int
    stdout_file: str
    stderr_file: str
    manifest_file: str


def _validated(
    config: FlowExecutionConfig | None,
) -> FlowExecutionConfig:
    value = config or FlowExecutionConfig.from_environment()

    if value.execution_mode not in {"wsl", "native"}:
        raise ValueError("OPM_EXECUTION_MODE 只能是 wsl 或 native")

    if value.timeout_seconds <= 0:
        raise ValueError("OPM_FLOW_TIMEOUT_SECONDS 必须大于 0")

    if not value.flow_command:
        raise ValueError("OPM_FLOW_COMMAND 不能为空")

    if value.execution_mode == "wsl" and not value.wsl_distribution:
        raise ValueError("WSL 执行模式下 OPM_WSL_DISTRIBUTION 不能为空")

    return value


def _effective_execution_mode(
    config: FlowExecutionConfig,
) -> str:
    """
    返回实际执行模式。

    Windows 中的 wsl 模式：
        使用 wsl.exe 进入指定发行版执行 Flow。

    已经处于 WSL/Linux 中：
        即使配置值仍为 wsl，也直接使用当前 Linux 环境中的 Flow，
        防止再次调用 wsl.exe，并避免将 /mnt/... 路径重复转换。
    """
    if config.execution_mode == "wsl" and os.name != "nt":
        return "native"

    return config.execution_mode


def windows_path_to_wsl(path: str | Path) -> str:
    """
    将 Windows 绝对路径转换为 WSL 挂载路径。

    示例：
        F:\\Projects\\petro-agent\\model.DATA
        -> /mnt/f/Projects/petro-agent/model.DATA

    已经是 Linux/WSL 绝对路径时直接返回。
    """
    raw_path = str(path)

    if os.name != "nt" and raw_path.startswith("/"):
        return str(Path(raw_path).expanduser().resolve())

    resolved = Path(path).expanduser().resolve()
    resolved_text = str(resolved)

    # 兼容传入已经转换好的 WSL 路径。
    if resolved_text.startswith("/"):
        return resolved_text

    drive = resolved.drive.rstrip(":")
    if not drive:
        raise ValueError(f"无法转换为 WSL 路径：{resolved}")

    tail = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive.lower()}{tail}"


def _version_command(
    config: FlowExecutionConfig,
) -> list[str]:
    mode = _effective_execution_mode(config)

    if mode == "wsl":
        return [
            "wsl.exe",
            "-d",
            config.wsl_distribution,
            "--",
            config.flow_command,
            "--version",
        ]

    return [
        config.flow_command,
        "--version",
    ]


def inspect_flow_environment(
    config: FlowExecutionConfig | None = None,
) -> FlowEnvironment:
    cfg = _validated(config)
    mode = _effective_execution_mode(cfg)

    host_command = (
        "wsl.exe"
        if mode == "wsl"
        else cfg.flow_command
    )

    executable = shutil.which(host_command)

    if executable is None:
        return FlowEnvironment(
            execution_mode=mode,
            distribution=(
                cfg.wsl_distribution
                if mode == "wsl"
                else None
            ),
            executable=None,
            available=False,
            version=None,
            reason=f"未找到主机命令：{host_command}",
        )

    try:
        completed = subprocess.run(
            _version_command(cfg),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return FlowEnvironment(
            execution_mode=mode,
            distribution=(
                cfg.wsl_distribution
                if mode == "wsl"
                else None
            ),
            executable=executable,
            available=False,
            version=None,
            reason="Flow 环境检查超时。",
        )
    except OSError as exc:
        return FlowEnvironment(
            execution_mode=mode,
            distribution=(
                cfg.wsl_distribution
                if mode == "wsl"
                else None
            ),
            executable=executable,
            available=False,
            version=None,
            reason=f"无法执行 Flow 环境检查：{exc}",
        )

    version = (
        completed.stdout or completed.stderr
    ).strip() or None

    return FlowEnvironment(
        execution_mode=mode,
        distribution=(
            cfg.wsl_distribution
            if mode == "wsl"
            else None
        ),
        executable=executable,
        available=completed.returncode == 0,
        version=version,
        reason=(
            None
            if completed.returncode == 0
            else f"Flow 检查失败，退出码为 {completed.returncode}。"
        ),
    )


def build_flow_command(
    deck_file: str | Path,
    output_dir: str | Path,
    config: FlowExecutionConfig,
    extra_args: Sequence[str] = (),
) -> list[str]:
    deck = Path(deck_file).expanduser().resolve()
    target = Path(output_dir).expanduser().resolve()
    mode = _effective_execution_mode(config)

    if mode == "wsl":
        return [
            "wsl.exe",
            "-d",
            config.wsl_distribution,
            "--",
            config.flow_command,
            windows_path_to_wsl(deck),
            f"--output-dir={windows_path_to_wsl(target)}",
            "--enable-esmry=true",
            *extra_args,
        ]

    return [
        config.flow_command,
        str(deck),
        f"--output-dir={target}",
        "--enable-esmry=true",
        *extra_args,
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for block in iter(
            lambda: source.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def run_flow(
    deck_file: str | Path,
    output_dir: str | Path,
    *,
    config: FlowExecutionConfig | None = None,
    extra_args: Sequence[str] = (),
    environment: Mapping[str, str] | None = None,
) -> FlowRunResult:
    deck = Path(deck_file).expanduser().resolve()

    if not deck.is_file() or deck.suffix.upper() != ".DATA":
        raise ValueError(
            f"Deck 文件不存在或不是 .DATA 文件：{deck}"
        )

    cfg = _validated(config)
    flow = inspect_flow_environment(cfg)

    if not flow.available:
        raise RuntimeError(
            flow.reason or "Flow 执行环境不可用。"
        )

    target = Path(output_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    stdout_file = target / "flow.stdout.log"
    stderr_file = target / "flow.stderr.log"
    manifest_file = target / "run_manifest.json"

    command = build_flow_command(
        deck,
        target,
        cfg,
        extra_args,
    )

    process_env = os.environ.copy()
    if environment:
        process_env.update(environment)

    started_at = datetime.now(timezone.utc)

    try:
        completed = subprocess.run(
            command,
            cwd=str(deck.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=process_env,
            timeout=cfg.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (
            exc.stderr
            or f"Flow 运行超过 {cfg.timeout_seconds} 秒，已终止。"
        )

        # 某些 Python 版本在文本模式超时时仍可能返回 bytes。
        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                "utf-8",
                errors="replace",
            )

        completed = subprocess.CompletedProcess(
            command,
            124,
            stdout,
            stderr,
        )

    finished_at = datetime.now(timezone.utc)

    stdout_file.write_text(
        completed.stdout or "",
        encoding="utf-8",
    )
    stderr_file.write_text(
        completed.stderr or "",
        encoding="utf-8",
    )

    manifest_file.write_text(
        json.dumps(
            {
                "deck_file": str(deck),
                "deck_sha256": _sha256(deck),
                "opm_flow_version": flow.version,
                # 记录实际执行模式，而不是原始配置模式。
                "execution_mode": flow.execution_mode,
                "configured_execution_mode": cfg.execution_mode,
                "wsl_distribution": flow.distribution,
                "executable": flow.executable,
                "command": command,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "return_code": completed.returncode,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    (target / "opm_flow_version.txt").write_text(
        (flow.version or "unknown") + "\n",
        encoding="utf-8",
    )

    return FlowRunResult(
        command=command,
        return_code=completed.returncode,
        stdout_file=str(stdout_file),
        stderr_file=str(stderr_file),
        manifest_file=str(manifest_file),
    )