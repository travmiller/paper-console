import os
from pathlib import Path
import subprocess

from app import printer_uart


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "wifi_ap_nmcli.sh"
)


def _migration_env(tmp_path: Path) -> tuple[dict[str, str], dict[str, Path]]:
    boot_dir = tmp_path / "boot"
    boot_dir.mkdir()
    config_file = boot_dir / "config.txt"
    cmdline_file = boot_dir / "cmdline.txt"
    serial_target = tmp_path / "ttyS0"
    serial_target.touch()
    serial0_path = tmp_path / "serial0"
    serial0_path.symlink_to(serial_target)
    boot_id_file = tmp_path / "boot-id"
    boot_id_file.write_text("boot-a\n", encoding="utf-8")

    config_file.write_text("[all]\nenable_uart=1\n", encoding="utf-8")
    cmdline_file.write_text(
        "console=serial0,115200 console=tty1 root=PARTUUID=test rootwait quiet\n",
        encoding="utf-8",
    )

    paths = {
        "config": config_file,
        "cmdline": cmdline_file,
        "serial0": serial0_path,
        "boot_id": boot_id_file,
        "state": tmp_path / "state" / "printer-uart-boot-id",
        "backups": tmp_path / "backups",
        "setup_marker": tmp_path / "setup-in-progress",
    }
    env = {
        **os.environ,
        "PC1_BOOT_CONFIG_FILE": str(paths["config"]),
        "PC1_BOOT_CMDLINE_FILE": str(paths["cmdline"]),
        "PC1_PRINTER_UART_BACKUP_DIR": str(paths["backups"]),
        "PC1_PRINTER_UART_STATE_FILE": str(paths["state"]),
        "PC1_PRINTER_UART_SETUP_MARKER": str(paths["setup_marker"]),
        "PC1_SERIAL0_PATH": str(paths["serial0"]),
        "PC1_BOOT_ID_FILE": str(paths["boot_id"]),
        "PC1_SYSTEMCTL_BIN": "/usr/bin/true",
        "PC1_SYSTEMD_RUN_BIN": "/usr/bin/true",
    }
    return env, paths


def _run_helper(command: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT_PATH), command],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_uart_migration_is_backed_up_and_idempotent(tmp_path):
    env, paths = _migration_env(tmp_path)

    first = _run_helper("ensure-printer-uart", env)
    second = _run_helper("ensure-printer-uart", env)

    assert first.returncode == 0
    assert "status=reboot_required" in first.stdout
    assert "changed=1" in first.stdout
    assert second.returncode == 0
    assert "status=reboot_required" in second.stdout
    assert "changed=0" in second.stdout

    config_text = paths["config"].read_text(encoding="utf-8")
    assert config_text.count("# BEGIN PC-1 PRINTER UART") == 1
    assert config_text.count("dtoverlay=disable-bt") == 1
    assert "console=serial0" not in paths["cmdline"].read_text(encoding="utf-8")
    assert "console=tty1" in paths["cmdline"].read_text(encoding="utf-8")
    assert (paths["backups"] / "config.txt.before-printer-uart").exists()
    assert (paths["backups"] / "cmdline.txt.before-printer-uart").exists()


def test_uart_migration_tracks_pending_reboot_then_clears_on_pl011(tmp_path):
    env, paths = _migration_env(tmp_path)
    assert _run_helper("ensure-printer-uart", env).returncode == 0

    scheduled = _run_helper("schedule-printer-uart-reboot", env)
    pending = _run_helper("ensure-printer-uart", env)

    assert scheduled.returncode == 0
    assert "reboot_scheduled=true" in scheduled.stdout
    assert paths["state"].read_text(encoding="utf-8").strip() == "boot-a"
    assert pending.returncode == 0
    assert "status=reboot_pending" in pending.stdout
    assert "reboot_pending=1" in pending.stdout

    paths["serial0"].unlink()
    pl011_target = paths["serial0"].parent / "ttyAMA0"
    pl011_target.touch()
    paths["serial0"].symlink_to(pl011_target)
    paths["boot_id"].write_text("boot-b\n", encoding="utf-8")

    ready = _run_helper("ensure-printer-uart", env)

    assert ready.returncode == 0
    assert "status=ready" in ready.stdout
    assert "serial_target=ttyAMA0" in ready.stdout
    assert not paths["state"].exists()


def test_uart_migration_does_not_loop_when_pl011_fails_after_reboot(tmp_path):
    env, paths = _migration_env(tmp_path)
    assert _run_helper("ensure-printer-uart", env).returncode == 0
    assert _run_helper("schedule-printer-uart-reboot", env).returncode == 0
    paths["boot_id"].write_text("boot-b\n", encoding="utf-8")

    failed = _run_helper("ensure-printer-uart", env)

    assert failed.returncode == 2
    assert "status=failed" in failed.stdout
    assert "error=pl011_not_active_after_reboot" in failed.stdout
    assert "reboot_required=1" not in failed.stdout


def test_uart_migration_defers_reboot_during_initial_setup(tmp_path):
    env, paths = _migration_env(tmp_path)
    paths["setup_marker"].touch()

    result = _run_helper("schedule-printer-uart-reboot", env)

    assert result.returncode == 3
    assert "error=setup_in_progress" in result.stdout
    assert not paths["state"].exists()


def test_prepare_printer_uart_schedules_required_reboot(monkeypatch):
    commands = []

    def fake_run(command):
        commands.append(command)
        if command == "ensure-printer-uart":
            return subprocess.CompletedProcess(
                args=[command],
                returncode=0,
                stdout=(
                    "status=reboot_required\n"
                    "reboot_required=1\n"
                    "reboot_pending=0\n"
                    "serial_target=ttyS0\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=[command],
            returncode=0,
            stdout="reboot_scheduled=true\n",
            stderr="",
        )

    monkeypatch.setattr(printer_uart, "_run_helper", fake_run)

    result = printer_uart.prepare_printer_uart()

    assert commands == ["ensure-printer-uart", "schedule-printer-uart-reboot"]
    assert result.reboot_scheduled is True
    assert result.suppress_printer_output is True


def test_prepare_printer_uart_does_not_reschedule_pending_reboot(monkeypatch):
    commands = []

    def fake_run(command):
        commands.append(command)
        return subprocess.CompletedProcess(
            args=[command],
            returncode=0,
            stdout=(
                "status=reboot_pending\n"
                "reboot_required=0\n"
                "reboot_pending=1\n"
                "serial_target=ttyS0\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(printer_uart, "_run_helper", fake_run)

    result = printer_uart.prepare_printer_uart()

    assert commands == ["ensure-printer-uart"]
    assert result.reboot_pending is True
    assert result.suppress_printer_output is True
