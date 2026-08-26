"""One-time Raspberry Pi printer UART migration support.

The privileged shell helper owns boot-file edits. This module only interprets
its machine-readable status and schedules the guarded reboot when needed.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import subprocess


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrinterUartPreparation:
    status: str = "unavailable"
    serial_target: str = "unknown"
    reboot_required: bool = False
    reboot_pending: bool = False
    reboot_scheduled: bool = False
    error: str = ""

    @property
    def suppress_printer_output(self) -> bool:
        """Avoid touching the old UART while a migration reboot is pending."""
        return self.reboot_pending or self.reboot_scheduled


def _helper_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "wifi_ap_nmcli.sh"


def _parse_helper_output(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in output.splitlines():
        key, separator, value = raw_line.partition("=")
        if separator and key.strip():
            values[key.strip()] = value.strip()
    return values


def _run_helper(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sudo", "-n", "/bin/bash", str(_helper_path()), command],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def prepare_printer_uart() -> PrinterUartPreparation:
    """Ensure PL011 configuration and schedule at most one migration reboot."""
    try:
        ensure_result = _run_helper("ensure-printer-uart")
    except Exception as exc:
        logger.warning("Printer UART migration helper could not run: %s", exc)
        return PrinterUartPreparation(error=str(exc))

    values = _parse_helper_output(ensure_result.stdout)
    status = values.get("status", "failed")
    error = values.get("error", "")
    serial_target = values.get("serial_target", "unknown")
    reboot_required = values.get("reboot_required") == "1"
    reboot_pending = values.get("reboot_pending") == "1"

    if ensure_result.returncode != 0:
        detail = error or (ensure_result.stderr or ensure_result.stdout).strip()[:300]
        logger.warning(
            "Printer UART migration is unavailable (status=%s): %s",
            status,
            detail or f"helper exited {ensure_result.returncode}",
        )
        return PrinterUartPreparation(
            status=status,
            serial_target=serial_target,
            error=detail,
        )

    reboot_scheduled = False
    if reboot_required:
        try:
            schedule_result = _run_helper("schedule-printer-uart-reboot")
            schedule_values = _parse_helper_output(schedule_result.stdout)
            reboot_scheduled = (
                schedule_result.returncode == 0
                and schedule_values.get("reboot_scheduled") == "true"
            )
            if not reboot_scheduled:
                error = schedule_values.get("error") or (
                    schedule_result.stderr or schedule_result.stdout
                ).strip()[:300]
                logger.warning("Printer UART reboot could not be scheduled: %s", error)
        except Exception as exc:
            error = str(exc)
            logger.warning("Printer UART reboot scheduling failed: %s", exc)

    preparation = PrinterUartPreparation(
        status=status,
        serial_target=serial_target,
        reboot_required=reboot_required,
        reboot_pending=reboot_pending,
        reboot_scheduled=reboot_scheduled,
        error=error,
    )
    if preparation.suppress_printer_output:
        logger.warning(
            "PL011 printer UART migration reboot pending; suppressing printer output"
        )
    elif status == "ready":
        logger.info("Printer UART ready on %s", serial_target)
    return preparation
