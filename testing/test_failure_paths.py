"""Regression tests for hardware/network failure paths."""

import asyncio
import importlib.util
import json
import subprocess
import sys
import time
import imaplib
import types
from pathlib import Path

import app.main as main_module
import app.wifi_manager as wifi_manager
from app.config import CalendarConfig, ChannelConfig, ChannelModuleAssignment, ModuleInstance
from app.drivers.printer_serial import PrinterDriver
from app.drivers.printer_mock import PrinterDriver as MockPrinterDriver
from app.modules import email_client
from app.modules import quotes as quotes_module
from app.modules import news as news_module
from app.modules import calendar as calendar_module
from app.modules import history as history_module
from app import factory_reset as factory_reset_module
from datetime import datetime, timedelta, timezone


def _completed(returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["nmcli"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_connect_to_wifi_returns_false_when_profile_creation_fails(monkeypatch):
    def fake_run_command(cmd, check=False):  # noqa: ARG001
        if "add" in cmd:
            return _completed(returncode=1, stderr="failed to create profile")
        return _completed(returncode=0)

    monkeypatch.setattr(wifi_manager, "run_command", fake_run_command)

    assert wifi_manager.connect_to_wifi("TestSSID", "password123") is False


def test_start_ap_mode_retries_then_succeeds(monkeypatch):
    start_attempts = {"count": 0}

    def fake_run_command(cmd, check=False):  # noqa: ARG001
        if cmd[-1] == "start":
            start_attempts["count"] += 1
            if start_attempts["count"] < 2:
                return _completed(returncode=1, stderr="first start failed")
        return _completed(returncode=0)

    monkeypatch.setattr(wifi_manager, "run_command", fake_run_command)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    assert wifi_manager.start_ap_mode(retries=3, retry_delay=0) is True
    assert start_attempts["count"] == 2


def test_start_ap_mode_returns_false_after_all_retries(monkeypatch):
    def fake_run_command(cmd, check=False):  # noqa: ARG001
        if cmd[-1] == "start":
            return _completed(returncode=1, stderr="all starts failed")
        return _completed(returncode=0)

    monkeypatch.setattr(wifi_manager, "run_command", fake_run_command)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    assert wifi_manager.start_ap_mode(retries=2, retry_delay=0) is False


def test_check_wifi_startup_skips_duplicate_setup_receipt_on_first_boot(monkeypatch):
    sleep_calls = []
    print_calls = []
    ap_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    async def fake_print_setup():
        print_calls.append("setup")

    monkeypatch.setattr(main_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main_module.os.path, "exists", lambda _path: False)
    monkeypatch.setattr(
        main_module.wifi_manager,
        "get_wifi_status",
        lambda: {"connected": False, "mode": "client"},
    )
    monkeypatch.setattr(
        main_module.wifi_manager,
        "start_ap_mode",
        lambda retries=3: ap_calls.append(retries) or True,
    )
    monkeypatch.setattr(main_module, "print_setup_instructions", fake_print_setup)

    asyncio.run(main_module.check_wifi_startup())

    assert ap_calls == [3]
    assert print_calls == []
    assert sleep_calls == [10, 5]


def test_check_wifi_startup_prints_setup_receipt_on_regular_boot(monkeypatch):
    print_calls = []
    ap_calls = []

    async def fake_sleep(_seconds):
        return None

    async def fake_print_setup():
        print_calls.append("setup")

    monkeypatch.setattr(main_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main_module.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(
        main_module.wifi_manager,
        "get_wifi_status",
        lambda: {"connected": False, "mode": "client"},
    )
    monkeypatch.setattr(
        main_module.wifi_manager,
        "start_ap_mode",
        lambda retries=3: ap_calls.append(retries) or True,
    )
    monkeypatch.setattr(main_module, "print_setup_instructions", fake_print_setup)

    asyncio.run(main_module.check_wifi_startup())

    assert ap_calls == [3]
    assert print_calls == ["setup"]


def test_email_polling_loop_uses_configured_interval_for_auto_print(monkeypatch):
    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        raise asyncio.CancelledError

    module = types.SimpleNamespace(
        type="email",
        config={"auto_print_new": True, "polling_interval": 60},
    )

    monkeypatch.setattr(main_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main_module.settings, "modules", {"email-1": module})

    try:
        asyncio.run(main_module.email_polling_loop())
    except asyncio.CancelledError:
        pass

    assert sleep_calls == [60]


def test_get_current_version_reports_development_install_mode(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()

    monkeypatch.setattr(main_module, "_get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        main_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="abc123\n", stderr=""
        ),
    )

    result = asyncio.run(main_module.get_current_version())

    assert result["version"] == "abc123"
    assert result["install_mode"] == "development"
    assert result["can_convert_to_production"] is True


def test_get_current_version_reports_production_install_mode(monkeypatch, tmp_path):
    (tmp_path / ".version").write_text("v0.1.0\n", encoding="utf-8")

    monkeypatch.setattr(main_module, "_get_project_root", lambda: tmp_path)

    result = asyncio.run(main_module.get_current_version())

    assert result["version"] == "v0.1.0"
    assert result["install_mode"] == "production"
    assert result["can_convert_to_production"] is False


def test_fetch_release_data_prefers_latest_beta_release_when_beta_enabled(monkeypatch):
    captured = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"tag_name": "v0.1.9", "draft": False, "prerelease": False},
                {"tag_name": "v0.2.0-beta.1", "draft": False, "prerelease": True},
            ]

    def fake_requests_get(url, headers=None, timeout=None):  # noqa: ARG001
        captured["url"] = url
        return DummyResponse()

    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = main_module._fetch_release_data(
        "travmiller/paper-console",
        include_prerelease=True,
    )

    assert captured["url"].endswith("/releases")
    assert result["tag_name"] == "v0.2.0-beta.1"


def test_fetch_release_data_uses_stable_release_when_beta_lane_has_no_prerelease(
    monkeypatch,
):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"tag_name": "v0.1.9", "draft": False, "prerelease": False},
                {"tag_name": "v0.1.8", "draft": False, "prerelease": False},
            ]

    def fake_requests_get(url, headers=None, timeout=None):  # noqa: ARG001
        assert url.endswith("/releases")
        return DummyResponse()

    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = main_module._fetch_release_data(
        "travmiller/paper-console",
        include_prerelease=True,
    )

    assert result["tag_name"] == "v0.1.9"


def test_fetch_release_data_prefers_stable_over_matching_prerelease(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"tag_name": "v0.2.10-beta.1", "draft": False, "prerelease": True},
                {"tag_name": "v0.2.10", "draft": False, "prerelease": False},
                {"tag_name": "v0.2.9", "draft": False, "prerelease": False},
            ]

    def fake_requests_get(url, headers=None, timeout=None):  # noqa: ARG001
        assert url.endswith("/releases")
        return DummyResponse()

    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = main_module._fetch_release_data(
        "travmiller/paper-console",
        include_prerelease=True,
    )

    assert result["tag_name"] == "v0.2.10"


def test_fetch_release_data_uses_highest_semver_not_release_order(monkeypatch):
    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"tag_name": "v0.2.10", "draft": False, "prerelease": False},
                {"tag_name": "v0.2.11-beta.2", "draft": False, "prerelease": True},
                {"tag_name": "v0.2.11-beta.1", "draft": False, "prerelease": True},
            ]

    def fake_requests_get(url, headers=None, timeout=None):  # noqa: ARG001
        assert url.endswith("/releases")
        return DummyResponse()

    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = main_module._fetch_release_data(
        "travmiller/paper-console",
        include_prerelease=True,
    )

    assert result["tag_name"] == "v0.2.11-beta.2"


def test_check_for_updates_uses_beta_channel_in_production(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    app_dir = project_root / "app"
    app_dir.mkdir(parents=True)
    fake_main_path = app_dir / "main.py"
    fake_main_path.write_text("# test stub\n", encoding="utf-8")
    (project_root / ".version").write_text("v0.1.0\n", encoding="utf-8")

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"tag_name": "v0.2.0-beta.1", "draft": False, "prerelease": True},
                {"tag_name": "v0.1.9", "draft": False, "prerelease": False},
            ]

    def fake_requests_get(url, headers=None, timeout=None):  # noqa: ARG001
        assert url.endswith("/releases")
        return DummyResponse()

    monkeypatch.setattr(main_module, "__file__", str(fake_main_path))
    monkeypatch.setattr(
        main_module,
        "settings",
        types.SimpleNamespace(release_channel="beta"),
        raising=False,
    )
    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = asyncio.run(main_module.check_for_updates())

    assert result["available"] is True
    assert result["current_version"] == "v0.1.0"
    assert result["latest_version"] == "v0.2.0-beta.1"
    assert result["release_channel"] == "beta"


def test_check_for_updates_falls_back_to_stable_when_beta_lane_has_no_prerelease(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "project"
    app_dir = project_root / "app"
    app_dir.mkdir(parents=True)
    fake_main_path = app_dir / "main.py"
    fake_main_path.write_text("# test stub\n", encoding="utf-8")
    (project_root / ".version").write_text("v0.1.0\n", encoding="utf-8")

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"tag_name": "v0.1.9", "draft": False, "prerelease": False},
            ]

    def fake_requests_get(url, headers=None, timeout=None):  # noqa: ARG001
        assert url.endswith("/releases")
        return DummyResponse()

    monkeypatch.setattr(main_module, "__file__", str(fake_main_path))
    monkeypatch.setattr(
        main_module,
        "settings",
        types.SimpleNamespace(release_channel="beta"),
        raising=False,
    )
    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = asyncio.run(main_module.check_for_updates())

    assert result["available"] is True
    assert result["current_version"] == "v0.1.0"
    assert result["latest_version"] == "v0.1.9"
    assert result["release_channel"] == "beta"


def test_check_for_updates_does_not_offer_semver_downgrade(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    app_dir = project_root / "app"
    app_dir.mkdir(parents=True)
    fake_main_path = app_dir / "main.py"
    fake_main_path.write_text("# test stub\n", encoding="utf-8")
    (project_root / ".version").write_text("v0.2.11-beta.2\n", encoding="utf-8")

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"tag_name": "v0.2.10", "draft": False, "prerelease": False},
            ]

    def fake_requests_get(url, headers=None, timeout=None):  # noqa: ARG001
        assert url.endswith("/releases")
        return DummyResponse()

    monkeypatch.setattr(main_module, "__file__", str(fake_main_path))
    monkeypatch.setattr(
        main_module,
        "settings",
        types.SimpleNamespace(release_channel="stable"),
        raising=False,
    )
    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = asyncio.run(main_module.check_for_updates())

    assert result["available"] is False
    assert result["up_to_date"] is True
    assert result["current_version"] == "v0.2.11-beta.2"
    assert result["latest_version"] == "v0.2.10"
    assert result["release_channel"] == "stable"


def test_convert_to_production_installs_release_and_removes_git(monkeypatch, tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    restart_calls = []
    captured = {}

    monkeypatch.setattr(main_module, "_get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        main_module,
        "settings",
        types.SimpleNamespace(release_channel="stable"),
        raising=False,
    )

    def fake_install_release_bundle(
        project_root,
        release_repo,
        *,
        expected_sha="",
        release_tag="",
        include_prerelease=False,
    ):
        captured["project_root"] = project_root
        captured["release_repo"] = release_repo
        captured["expected_sha"] = expected_sha
        captured["release_tag"] = release_tag
        captured["include_prerelease"] = include_prerelease
        (project_root / ".version").write_text("v0.1.0\n", encoding="utf-8")
        return "v0.1.0"

    monkeypatch.setattr(main_module, "_install_release_bundle", fake_install_release_bundle)
    monkeypatch.setattr(
        main_module,
        "_install_update_dependencies",
        lambda project_root, is_dev: subprocess.CompletedProcess(
            args=["pip"], returncode=0, stdout="", stderr=""
        ),
    )
    monkeypatch.setattr(main_module, "_restart_pc1_service", lambda: restart_calls.append(True))

    result = asyncio.run(main_module.convert_to_production_updates())

    assert result["success"] is True
    assert captured["project_root"] == tmp_path
    assert captured["release_repo"] == "travmiller/paper-console"
    assert captured["expected_sha"] == ""
    assert captured["release_tag"] == ""
    assert captured["include_prerelease"] is False
    assert not git_dir.exists()
    assert restart_calls == [True]


def test_convert_to_production_keeps_git_when_dependency_install_fails(monkeypatch, tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    restart_calls = []

    monkeypatch.setattr(main_module, "_get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        main_module,
        "_install_release_bundle",
        lambda project_root, release_repo, *, expected_sha="", release_tag="", include_prerelease=False: "v0.1.0",
    )
    monkeypatch.setattr(
        main_module,
        "_install_update_dependencies",
        lambda project_root, is_dev: subprocess.CompletedProcess(
            args=["pip"], returncode=1, stdout="", stderr="failed"
        ),
    )
    monkeypatch.setattr(main_module, "_restart_pc1_service", lambda: restart_calls.append(True))

    result = asyncio.run(main_module.convert_to_production_updates())

    assert result["success"] is False
    assert git_dir.exists()
    assert restart_calls == []


def test_install_updates_uses_beta_release_channel_in_production(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    captured = {}

    monkeypatch.setattr(main_module, "_get_project_root", lambda: project_root)
    monkeypatch.setattr(
        main_module,
        "settings",
        types.SimpleNamespace(release_channel="beta"),
        raising=False,
    )

    def fake_install_release_bundle(
        current_project_root,
        release_repo,
        *,
        expected_sha="",
        release_tag="",
        include_prerelease=False,
    ):
        captured["project_root"] = current_project_root
        captured["release_repo"] = release_repo
        captured["expected_sha"] = expected_sha
        captured["release_tag"] = release_tag
        captured["include_prerelease"] = include_prerelease
        return "v0.2.0-beta.1"

    monkeypatch.setattr(main_module, "_install_release_bundle", fake_install_release_bundle)
    monkeypatch.setattr(
        main_module,
        "_install_update_dependencies",
        lambda current_project_root, is_dev: subprocess.CompletedProcess(
            args=["pip"], returncode=0, stdout="", stderr=""
        ),
    )
    monkeypatch.setattr(main_module, "_restart_pc1_service", lambda: None)

    result = asyncio.run(main_module.install_updates())

    assert result["success"] is True
    assert captured["project_root"] == project_root
    assert captured["release_repo"] == "travmiller/paper-console"
    assert captured["expected_sha"] == ""
    assert captured["release_tag"] == ""
    assert captured["include_prerelease"] is True


def test_try_begin_print_job_respects_hold_reservation(monkeypatch):
    monkeypatch.setattr(main_module, "print_in_progress", False)
    monkeypatch.setattr(main_module, "hold_action_in_progress", True)
    monkeypatch.setattr(main_module, "hold_action_started_at", time.time())
    monkeypatch.setattr(main_module, "last_print_time", 0.0)

    assert main_module._try_begin_print_job(debounce=False) is False

    monkeypatch.setattr(main_module, "hold_action_in_progress", False)
    assert main_module._try_begin_print_job(debounce=False) is True

    main_module._clear_print_reservation()
    assert main_module.print_in_progress is False
    assert main_module.hold_action_in_progress is False
    assert main_module.hold_action_started_at == 0.0


def test_clear_print_reservation_updates_debounce_from_completion(monkeypatch):
    now = 1_000.0
    drained = []

    class FakeButton:
        def drain_pending_events(self):
            drained.append("drained")

    monkeypatch.setattr(main_module.time, "time", lambda: now)
    monkeypatch.setattr(main_module, "button", FakeButton())
    monkeypatch.setattr(main_module, "print_in_progress", True)
    monkeypatch.setattr(main_module, "hold_action_in_progress", False)
    monkeypatch.setattr(main_module, "hold_action_started_at", 0.0)
    monkeypatch.setattr(main_module, "last_print_time", 0.0)

    main_module._clear_print_reservation(clear_hold=False)

    assert main_module.print_in_progress is False
    assert main_module.last_print_time == now
    assert drained == ["drained"]


def test_try_begin_print_job_clears_stale_hold_reservation(monkeypatch):
    now = 1_000.0

    monkeypatch.setattr(main_module.time, "time", lambda: now)
    monkeypatch.setattr(main_module, "print_in_progress", False)
    monkeypatch.setattr(main_module, "hold_action_in_progress", True)
    monkeypatch.setattr(
        main_module,
        "hold_action_started_at",
        now - main_module.HOLD_ACTION_TIMEOUT_SECONDS - 1,
    )
    monkeypatch.setattr(main_module, "last_print_time", 0.0)

    assert main_module._try_begin_print_job(debounce=False) is True
    assert main_module.print_in_progress is True
    assert main_module.hold_action_in_progress is False
    assert main_module.hold_action_started_at == 0.0

    main_module._clear_print_reservation()


def test_on_factory_reset_threadsafe_promotes_hold_reservation(monkeypatch):
    captured = {}

    class DummyLoop:
        def is_running(self):
            return True

    def fake_run_coroutine_threadsafe(coro, loop):
        captured["coro"] = coro
        captured["loop"] = loop
        return None

    monkeypatch.setattr(main_module, "global_loop", DummyLoop())
    monkeypatch.setattr(main_module, "print_in_progress", False)
    monkeypatch.setattr(main_module, "hold_action_in_progress", True)
    monkeypatch.setattr(main_module, "hold_action_started_at", time.time())
    monkeypatch.setattr(main_module.asyncio, "run_coroutine_threadsafe", fake_run_coroutine_threadsafe)

    main_module.on_factory_reset_threadsafe()

    assert main_module.print_in_progress is True
    assert main_module.hold_action_in_progress is False
    assert main_module.hold_action_started_at == 0.0
    assert captured["loop"] is main_module.global_loop
    captured["coro"].close()

    main_module._clear_print_reservation()


def test_long_press_menu_trigger_drains_pending_button_events_before_unlock(monkeypatch):
    order = []

    class FakePrinter:
        def clear_hardware_buffer(self):
            order.append("clear_hw")

    class FakeDial:
        def read_position(self):
            return 5

    class FakeButton:
        def drain_pending_events(self):
            order.append("drain")

    class ImmediateExecutor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeLoop:
        async def run_in_executor(self, executor, fn):
            order.append("run_in_executor")
            fn()

    monkeypatch.setattr(main_module, "printer", FakePrinter())
    monkeypatch.setattr(main_module, "dial", FakeDial())
    monkeypatch.setattr(main_module, "button", FakeButton())
    monkeypatch.setattr(main_module, "_print_long_press_menu", lambda pos: order.append(f"print_menu_{pos}"))
    monkeypatch.setattr(
        main_module,
        "_clear_print_reservation",
        lambda clear_hold=False: order.append(f"clear_reservation_{clear_hold}"),
    )

    monkeypatch.setattr(main_module.asyncio, "get_event_loop", lambda: FakeLoop())
    monkeypatch.setattr(main_module, "ThreadPoolExecutor", ImmediateExecutor, raising=False)

    import app.selection_mode as selection_mode

    monkeypatch.setattr(selection_mode, "exit_selection_mode", lambda: order.append("exit_selection_mode"))
    monkeypatch.setattr(
        selection_mode,
        "enter_selection_mode",
        lambda callback, module_id, **kwargs: order.append(f"enter_selection_mode_{module_id}"),
    )

    original_executor = getattr(__import__("concurrent.futures", fromlist=["ThreadPoolExecutor"]), "ThreadPoolExecutor")
    monkeypatch.setattr("concurrent.futures.ThreadPoolExecutor", ImmediateExecutor)

    asyncio.run(main_module.long_press_menu_trigger())

    assert order == [
        "exit_selection_mode",
        "run_in_executor",
        "print_menu_5",
        "drain",
        "enter_selection_mode_quick-actions-5",
        "clear_reservation_False",
    ]


def test_trigger_channel_does_not_hard_reset_printer_between_normal_jobs(monkeypatch):
    events = []

    class FakePrinter:
        def blip(self):
            events.append("blip")

        def clear_hardware_buffer(self):
            events.append("clear_hw")

        def reset_buffer(self, max_lines=0):
            events.append(f"reset_buffer_{max_lines}")

        def print_text(self, text):
            events.append(f"text:{text}")

        def print_line(self):
            events.append("line")

        def feed(self, count):
            events.append(f"feed:{count}")

        def flush_buffer(self):
            events.append("flush")

    monkeypatch.setattr(main_module, "printer", FakePrinter())
    monkeypatch.setattr(main_module, "settings", types.SimpleNamespace(max_print_lines=200, channels={1: None}))
    monkeypatch.setattr(main_module, "_clear_print_reservation", lambda clear_hold=False: None)

    asyncio.run(main_module.trigger_channel(1))

    assert "clear_hw" not in events


def test_scheduler_loop_skips_trigger_when_hold_reserved(monkeypatch):
    triggered = []
    sleep_calls = {"count": 0}

    class FrozenDateTime:
        @classmethod
        def now(cls):
            return datetime(2026, 4, 3, 12, 0)

    async def fake_sleep(_seconds):
        sleep_calls["count"] += 1
        if sleep_calls["count"] == 1:
            return None
        raise asyncio.CancelledError

    async def fake_trigger_channel(position):
        triggered.append(position)

    monkeypatch.setattr(main_module, "datetime", FrozenDateTime)
    monkeypatch.setattr(main_module.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(main_module, "trigger_channel", fake_trigger_channel)
    monkeypatch.setattr(
        main_module.settings,
        "channels",
        {1: types.SimpleNamespace(schedule=["12:00"])},
    )
    monkeypatch.setattr(main_module, "print_in_progress", False)
    monkeypatch.setattr(main_module, "hold_action_in_progress", True)
    monkeypatch.setattr(
        main_module,
        "hold_action_started_at",
        time.time(),
    )

    try:
        asyncio.run(main_module.scheduler_loop())
    except asyncio.CancelledError:
        pass

    assert triggered == []
    main_module._clear_print_reservation()


def test_printer_driver_handles_serial_init_failure(monkeypatch):
    import serial

    monkeypatch.setattr(
        PrinterDriver,
        "_load_font_family",
        lambda self: {"regular": None, "bold": None},
    )
    monkeypatch.setattr(
        serial,
        "Serial",
        lambda *args, **kwargs: (_ for _ in ()).throw(serial.SerialException("no port")),
    )

    driver = PrinterDriver(port="COM99")
    assert driver.ser is None


def test_fetch_emails_sets_auth_failed_on_imap_auth_error(monkeypatch):
    config = {
        "email_service": "Custom",
        "email_user": "user@example.com",
        "email_password": "bad-password",
        "email_host": "imap.example.com",
        "email_port": 993,
        "email_use_ssl": True,
    }

    def fake_imap4_ssl(*args, **kwargs):  # noqa: ARG001
        raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", fake_imap4_ssl)

    messages = email_client.fetch_emails(config)
    assert messages == []
    assert email_client._LAST_FETCH_ERROR == "auth_failed"


def test_news_module_uses_configurable_country_and_page_size(monkeypatch):
    captured = {}

    class DummyResponse:
        def json(self):
            return {"status": "ok", "articles": []}

    def fake_get(url, params=None, timeout=0):  # noqa: ARG001
        captured["params"] = params or {}
        return DummyResponse()

    monkeypatch.setattr(news_module.requests, "get", fake_get)
    news_module.get_newsapi_articles(
        {
            "news_api_key": "abc123",
            "country": "ca",
            "page_size": 7,
        }
    )

    assert captured["params"]["country"] == "ca"
    assert captured["params"]["pageSize"] == 7


def test_calendar_rrule_respects_exdate_in_window():
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = now + timedelta(hours=9)
    skip = start + timedelta(days=1)

    dt_fmt = "%Y%m%dT%H%M%SZ"
    ics = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "BEGIN:VEVENT",
            f"DTSTART:{start.strftime(dt_fmt)}",
            "RRULE:FREQ=DAILY;COUNT=3",
            f"EXDATE:{skip.strftime(dt_fmt)}",
            "SUMMARY:Recurring test event",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )

    events = calendar_module.parse_events(ics, days_to_show=4, timezone_str="UTC")
    event_days = set(events.keys())

    assert start.date() in event_days
    assert skip.date() not in event_days
    assert (start + timedelta(days=2)).date() in event_days


def test_calendar_config_accepts_ui_sources_without_label():
    config = CalendarConfig(
        ical_sources=[
            {"url": "https://example.com/basic.ics"},
            {"name": "Home", "url": "https://example.com/home.ics"},
        ],
        view_mode="month",
    )

    assert [source.url for source in config.ical_sources] == [
        "https://example.com/basic.ics",
        "https://example.com/home.ics",
    ]
    assert config.ical_sources[1].name == "Home"


def test_fetch_ics_rejects_non_calendar_response(monkeypatch):
    class DummyResponse:
        text = "<html><title>Sign in</title></html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        calendar_module.requests,
        "get",
        lambda url, timeout=0: DummyResponse(),  # noqa: ARG005
    )

    assert calendar_module.fetch_ics("https://example.com/basic.ics") is None


def test_calendar_receipt_reports_unloadable_feed(monkeypatch, capsys):
    monkeypatch.setattr(calendar_module, "fetch_ics", lambda url: None)  # noqa: ARG005

    printer = MockPrinterDriver()
    calendar_module.format_calendar_receipt(
        printer,
        CalendarConfig(
            ical_sources=[{"url": "https://example.com/basic.ics"}],
            view_mode="month",
        ),
        "Calendar",
    )

    output = capsys.readouterr().out
    assert "Could not load calendar feed." in output
    assert "Check the iCal URL." in output
    assert "No upcoming events." not in output


def test_factory_reset_reports_reboot_failure(monkeypatch):
    deleted = []

    monkeypatch.setattr(factory_reset_module.os.path, "exists", lambda _p: True)
    monkeypatch.setattr(factory_reset_module.os, "remove", lambda p: deleted.append(p))
    monkeypatch.setattr(
        factory_reset_module.wifi_manager, "forget_all_wifi", lambda: True
    )
    monkeypatch.setattr(
        factory_reset_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["sudo", "reboot"], returncode=1, stdout="", stderr="sudo denied"
        ),
    )

    result = factory_reset_module.perform_factory_reset()

    assert result["config_cleared"] is True
    assert result["wifi_cleared"] is True
    assert result["reboot_requested"] is False
    assert any("Reboot command failed" in e for e in result["errors"])
    assert len(deleted) == 3


def test_factory_reset_success_path(monkeypatch):
    monkeypatch.setattr(factory_reset_module.os.path, "exists", lambda _p: False)
    monkeypatch.setattr(
        factory_reset_module.wifi_manager, "forget_all_wifi", lambda: True
    )
    monkeypatch.setattr(
        factory_reset_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=["sudo", "reboot"], returncode=0, stdout="", stderr=""
        ),
    )

    result = factory_reset_module.perform_factory_reset()

    assert result["config_cleared"] is True
    assert result["wifi_cleared"] is True
    assert result["reboot_requested"] is True
    assert result["errors"] == []


def test_factory_reset_resets_managed_device_password(monkeypatch, tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "config.json").write_text("{}", encoding="utf-8")
    (project_root / "config.json.bak").write_text("{}", encoding="utf-8")
    (project_root / ".welcome_printed").write_text("1\n", encoding="utf-8")

    password_file = tmp_path / "etc" / "pc1" / "device_password"
    managed_file = tmp_path / "etc" / "pc1" / "device_managed"
    password_file.parent.mkdir(parents=True)
    password_file.write_text("old-password\n", encoding="utf-8")
    managed_file.write_text("1\n", encoding="utf-8")

    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(
        factory_reset_module,
        "_project_base_dir",
        lambda: str(project_root),
    )
    monkeypatch.setattr(factory_reset_module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        factory_reset_module.wifi_manager, "forget_all_wifi", lambda: True
    )
    monkeypatch.setattr(
        factory_reset_module.device_password,
        "generate_device_password",
        lambda length=8: "freshpass",
    )
    monkeypatch.setenv("PC1_DEVICE_PASSWORD_FILE", str(password_file))
    monkeypatch.setenv("PC1_DEVICE_MANAGED_FILE", str(managed_file))
    monkeypatch.delenv("PC1_DEVICE_PASSWORD", raising=False)
    monkeypatch.setenv("USER", "pc1")
    monkeypatch.setattr(factory_reset_module.platform, "system", lambda: "Linux")

    result = factory_reset_module.perform_factory_reset()

    assert result["config_cleared"] is True
    assert result["device_password_reset"] is True
    assert result["wifi_cleared"] is True
    assert result["reboot_requested"] is True
    assert result["errors"] == []
    assert password_file.read_text(encoding="utf-8").strip() == "freshpass"
    assert calls[0][0] == ["sudo", "chpasswd"]
    assert calls[0][1]["input"] == "pc1:freshpass\n"
    assert calls[1][0] == ["sudo", "reboot"]


def test_install_update_dependencies_recreates_missing_repo_venv(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (project_root / "requirements-pi.txt").write_text(
        "-r requirements.txt\nRPi.GPIO\n",
        encoding="utf-8",
    )

    commands = []

    def fake_run(
        cmd, cwd=None, capture_output=False, text=False, timeout=None, check=False
    ):  # noqa: ARG001
        commands.append(cmd)
        if cmd[1:3] == ["-m", "venv"]:
            venv_python = project_root / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True, exist_ok=True)
            venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )
        if cmd[1:4] == ["-m", "pip", "install"]:
            assert cmd[-1] == str(project_root / "requirements-pi.txt")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="ok", stderr=""
            )
        raise AssertionError(f"Unexpected subprocess command: {cmd}")

    monkeypatch.setattr(
        main_module.shutil,
        "which",
        lambda name: "/usr/bin/python3" if name == "python3" else None,
    )
    monkeypatch.setattr(main_module.subprocess, "run", fake_run)

    result = main_module._install_update_dependencies(project_root, is_dev=False)

    assert result.returncode == 0
    assert any(cmd[1:3] == ["-m", "venv"] for cmd in commands)
    assert any(
        cmd[0] == str(project_root / ".venv" / "bin" / "python")
        and cmd[1:4] == ["-m", "pip", "install"]
        for cmd in commands
    )


def test_install_updates_does_not_restart_service_when_dependency_install_fails(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "project"
    (project_root / "app").mkdir(parents=True)
    (project_root / ".git").mkdir()
    fake_main_path = project_root / "app" / "main.py"
    fake_main_path.write_text("# test stub\n", encoding="utf-8")

    commands = []

    def fake_run(
        cmd, cwd=None, capture_output=False, text=False, timeout=None, check=False
    ):  # noqa: ARG001
        commands.append(cmd)
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="main\n", stderr=""
            )
        if cmd[:3] == ["git", "pull", "origin"]:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="Already up to date.\n", stderr=""
            )
        raise AssertionError(f"Unexpected subprocess command: {cmd}")

    monkeypatch.setattr(main_module, "__file__", str(fake_main_path))
    monkeypatch.setattr(main_module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        main_module,
        "_install_update_dependencies",
        lambda project_root, is_dev: subprocess.CompletedProcess(
            args=["python", "-m", "pip"], returncode=1, stdout="", stderr="pip failed"
        ),
    )
    monkeypatch.setattr(main_module.time, "sleep", lambda *_: None)

    result = asyncio.run(main_module.install_updates())

    assert result["success"] is False
    assert "Dependency installation failed" in result["error"]
    assert not any(cmd[:3] == ["sudo", "systemctl", "restart"] for cmd in commands)


def test_validate_production_update_bundle_rejects_missing_web_dist(tmp_path):
    source_dir = tmp_path / "bundle"
    (source_dir / "app").mkdir(parents=True)
    (source_dir / "run.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    try:
        main_module._validate_production_update_bundle(source_dir)
        raise AssertionError("Expected production bundle validation to fail")
    except RuntimeError as exc:
        assert "web/dist/index.html" in str(exc)


def test_install_updates_requires_explicit_production_release_asset(
    monkeypatch, tmp_path
):
    project_root = tmp_path / "project"
    (project_root / "app").mkdir(parents=True)
    fake_main_path = project_root / "app" / "main.py"
    fake_main_path.write_text("# test stub\n", encoding="utf-8")

    class DummyResponse:
        def __init__(self, status_code=200, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("http error")

        def json(self):
            return self._payload

    release_payload = {
        "tag_name": "v9.9.9",
        "draft": False,
        "prerelease": False,
        "assets": [{"name": "SHA256SUMS", "browser_download_url": "https://example.test/SHA256SUMS"}],
        "tarball_url": "https://example.test/source.tar.gz",
    }

    def fake_requests_get(url, headers=None, timeout=None, stream=False):  # noqa: ARG001
        assert stream is False
        return DummyResponse(payload=[release_payload])

    monkeypatch.setattr(main_module, "__file__", str(fake_main_path))
    monkeypatch.setitem(
        sys.modules,
        "requests",
        types.SimpleNamespace(get=fake_requests_get),
    )

    result = asyncio.run(main_module.install_updates())

    assert result["success"] is False
    assert "required production bundle asset" in result["error"]


def test_quotes_module_does_not_download_when_local_db_is_missing(monkeypatch):
    missing_path = Path("/tmp/pc1-missing-quotes.json")
    monkeypatch.setattr(quotes_module, "_get_quotes_db_path", lambda: missing_path)

    quote = quotes_module.get_random_quote()

    assert quote["quoteText"] == "Offline quotes database is missing."
    assert quote["quoteAuthor"] == "System"


def test_bundled_quotes_db_is_valid_utf8():
    bundled_path = quotes_module._get_quotes_db_path()
    with bundled_path.open("r", encoding="utf-8") as f:
        quotes = json.load(f)

    assert isinstance(quotes, list)
    assert quotes


def test_history_module_does_not_download_when_local_db_is_missing(monkeypatch):
    monkeypatch.setattr(history_module, "LOCAL_DB_PATH", Path("/tmp/pc1-missing-history.json"))

    events = history_module.get_events_for_today()

    assert events == ["Offline history database is missing."]


def test_release_build_validates_required_runtime_assets(monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "release_build.py"
    spec = importlib.util.spec_from_file_location("release_build_test_module", script_path)
    release_build = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(release_build)

    monkeypatch.setattr(release_build, "REQUIRED_RUNTIME_PATHS", ["missing/offline.json"])

    try:
        release_build.validate_runtime_assets()
        raise AssertionError("Expected runtime asset validation to fail")
    except FileNotFoundError as exc:
        assert "missing/offline.json" in str(exc)


def test_release_build_normalizes_mounted_windows_temp_env(monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "release_build.py"
    spec = importlib.util.spec_from_file_location("release_build_test_module", script_path)
    release_build = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(release_build)

    monkeypatch.setattr(release_build.os, "name", "posix", raising=False)
    monkeypatch.setenv("TEMP", "/mnt/c/Users/test/AppData/Local/Temp")
    monkeypatch.setenv("TMP", "/mnt/c/Users/test/AppData/Local/Temp")
    monkeypatch.delenv("TMPDIR", raising=False)

    env, normalized = release_build.build_subprocess_env()

    assert normalized is True
    assert env["TMPDIR"] == "/tmp"
    assert env["TEMP"] == "/tmp"
    assert env["TMP"] == "/tmp"


def test_release_build_preserves_local_temp_env(monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "release_build.py"
    spec = importlib.util.spec_from_file_location("release_build_test_module", script_path)
    release_build = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(release_build)

    monkeypatch.setattr(release_build.os, "name", "posix", raising=False)
    monkeypatch.setenv("TMPDIR", "/tmp/pc1-tests")
    monkeypatch.setenv("TEMP", "/tmp/pc1-tests")
    monkeypatch.setenv("TMP", "/tmp/pc1-tests")

    env, normalized = release_build.build_subprocess_env()

    assert normalized is False
    assert env["TMPDIR"] == "/tmp/pc1-tests"
    assert env["TEMP"] == "/tmp/pc1-tests"
    assert env["TMP"] == "/tmp/pc1-tests"


def test_selection_mode_ignores_overlapping_callbacks():
    import threading
    import app.selection_mode as selection_mode

    selection_mode.exit_selection_mode()
    started = threading.Event()
    release = threading.Event()
    calls = []
    results = []

    def slow_callback(dial_position):
        calls.append(dial_position)
        started.set()
        release.wait(timeout=1)

    selection_mode.enter_selection_mode(slow_callback, "busy-test")

    worker = threading.Thread(
        target=lambda: results.append(selection_mode.handle_selection(1))
    )
    worker.start()
    assert started.wait(timeout=1)

    results.append(selection_mode.handle_selection(2))
    release.set()
    worker.join(timeout=1)

    assert calls == [1]
    assert results.count(True) == 1
    assert results.count(False) == 1

    selection_mode.exit_selection_mode()


def test_execute_module_passes_instance_id_to_modules_that_accept_it(monkeypatch):
    from app.config import ModuleInstance

    captured = {}

    def fake_execute(printer, config, module_name, module_id=None):  # noqa: ARG001
        captured["module_id"] = module_id
        captured["module_name"] = module_name
        captured["config"] = config

    monkeypatch.setattr(
        main_module,
        "get_module_def",
        lambda module_type: types.SimpleNamespace(execute_fn=fake_execute),
    )

    module = ModuleInstance(
        id="adventure-one",
        type="adventure",
        name="Cave Run",
        config={"reset_game": False},
    )

    assert main_module.execute_module(module) is True
    assert captured == {
        "module_id": "adventure-one",
        "module_name": "Cave Run",
        "config": {"reset_game": False},
    }


def test_adventure_ignores_invalid_choice_without_printing(monkeypatch, tmp_path):
    import app.hardware as hardware
    import app.selection_mode as selection_mode
    from app.modules import adventure

    selection_mode.exit_selection_mode()

    class FakeButton:
        def __init__(self):
            self.drains = 0

        def drain_pending_events(self):
            self.drains += 1

    class FakePrinter:
        def __init__(self):
            self.bodies = []

        def reset_buffer(self, max_lines=0):  # noqa: ARG002
            return None

        def print_header(self, *args, **kwargs):  # noqa: ARG002
            return None

        def print_subheader(self, *args, **kwargs):  # noqa: ARG002
            return None

        def print_body(self, text):
            self.bodies.append(text)

        def print_caption(self, *args, **kwargs):  # noqa: ARG002
            return None

        def print_line(self):
            return None

        def feed(self, lines=1):  # noqa: ARG002
            return None

        def flush_buffer(self):
            return None

    fake_button = FakeButton()
    fake_printer = FakePrinter()

    monkeypatch.setattr(hardware, "button", fake_button)
    monkeypatch.setattr(hardware, "printer", fake_printer)
    monkeypatch.setattr(
        adventure,
        "_get_state_path",
        lambda module_id: tmp_path / f"{module_id}.json",
    )

    adventure.format_adventure_receipt(
        fake_printer,
        config={},
        module_name="ADVENTURE",
        module_id="adventure-one",
    )

    assert selection_mode.is_selection_mode_active() is True
    assert selection_mode.get_current_module_id() == "adventure-one"
    assert fake_button.drains == 1
    printed_before_invalid = list(fake_printer.bodies)

    assert selection_mode.can_handle_selection(7) is False
    assert selection_mode.handle_selection(7) is False

    assert selection_mode.is_selection_mode_active() is True
    assert selection_mode.get_current_module_id() == "adventure-one"
    assert fake_button.drains == 1
    assert fake_printer.bodies == printed_before_invalid

    selection_mode.exit_selection_mode()


def test_quick_actions_ignores_invalid_selection_without_printing(monkeypatch):
    order = []
    captured = {}

    class FakePrinter:
        def reset_buffer(self, max_lines=0):  # noqa: ARG002
            order.append("reset_buffer")

        def print_header(self, *args, **kwargs):  # noqa: ARG002
            order.append("print_header")

        def print_caption(self, *args, **kwargs):  # noqa: ARG002
            order.append("print_caption")

        def feed(self, lines=1):  # noqa: ARG002
            order.append("feed")

        def flush_buffer(self):
            order.append("flush_buffer")

    class FakeDial:
        def read_position(self):
            return 5

    class FakeButton:
        def drain_pending_events(self):
            order.append("drain")

    class ImmediateExecutor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeLoop:
        async def run_in_executor(self, executor, fn):
            order.append("run_in_executor")
            fn()

    def fake_enter_selection_mode(callback, module_id, valid_positions=None):
        captured["callback"] = callback
        captured["module_id"] = module_id
        captured["valid_positions"] = valid_positions
        order.append(f"enter_selection_mode_{module_id}")

    monkeypatch.setattr(main_module, "printer", FakePrinter())
    monkeypatch.setattr(main_module, "dial", FakeDial())
    monkeypatch.setattr(main_module, "button", FakeButton())
    monkeypatch.setattr(main_module, "_print_long_press_menu", lambda pos: order.append(f"print_menu_{pos}"))
    monkeypatch.setattr(
        main_module,
        "_clear_print_reservation",
        lambda clear_hold=False: order.append(f"clear_reservation_{clear_hold}"),
    )
    monkeypatch.setattr(main_module.asyncio, "get_event_loop", lambda: FakeLoop())

    import app.hardware as hardware
    import app.selection_mode as selection_mode

    monkeypatch.setattr(hardware, "printer", FakePrinter())
    monkeypatch.setattr(selection_mode, "exit_selection_mode", lambda: order.append("exit_selection_mode"))
    monkeypatch.setattr(selection_mode, "enter_selection_mode", fake_enter_selection_mode)
    monkeypatch.setattr("concurrent.futures.ThreadPoolExecutor", ImmediateExecutor)

    asyncio.run(main_module.long_press_menu_trigger())

    order.clear()
    captured["callback"](6)

    assert order == []
    assert captured["module_id"] == "quick-actions-5"
    assert captured["valid_positions"] == {1, 2, 3, 4, 5, 8}


def test_quick_factory_reset_confirmation_ignores_empty_slots(monkeypatch):
    import app.hardware as hardware
    import app.selection_mode as selection_mode

    events = []

    class FakePrinter:
        def reset_buffer(self, max_lines=0):  # noqa: ARG002
            events.append("reset_buffer")

        def print_header(self, *args, **kwargs):  # noqa: ARG002
            events.append("print_header")

        def print_line(self):
            events.append("print_line")

        def print_bold(self, *args, **kwargs):  # noqa: ARG002
            events.append("print_bold")

        def print_body(self, *args, **kwargs):  # noqa: ARG002
            events.append("print_body")

        def print_subheader(self, *args, **kwargs):  # noqa: ARG002
            events.append("print_subheader")

        def print_caption(self, *args, **kwargs):  # noqa: ARG002
            events.append("print_caption")

        def feed(self, lines=1):  # noqa: ARG002
            events.append("feed")

        def flush_buffer(self):
            events.append("flush_buffer")

    fake_printer = FakePrinter()
    monkeypatch.setattr(hardware, "printer", fake_printer)

    selection_mode.exit_selection_mode()
    main_module._confirm_quick_factory_reset(fake_printer, "quick-factory-reset")

    assert selection_mode.is_selection_mode_active() is True
    assert selection_mode.get_current_module_id() == "quick-factory-reset-reset-confirm"
    assert selection_mode.can_handle_selection(1) is True
    assert selection_mode.can_handle_selection(2) is False
    assert selection_mode.can_handle_selection(8) is True

    events.clear()
    assert selection_mode.handle_selection(2) is False
    assert events == []

    assert selection_mode.handle_selection(8) is True
    assert "reset_buffer" in events
    assert selection_mode.is_selection_mode_active() is False


def test_invalid_selection_position_does_not_blip(monkeypatch):
    import app.selection_mode as selection_mode

    calls = []

    class FakePrinter:
        def blip(self):
            calls.append("blip")

    selection_mode.exit_selection_mode()
    selection_mode.enter_selection_mode(
        lambda dial_position: calls.append(f"choice_{dial_position}"),
        "valid-position-test",
        valid_positions={1},
    )

    monkeypatch.setattr(main_module, "printer", FakePrinter())
    monkeypatch.setattr(
        main_module,
        "_clear_print_reservation",
        lambda clear_hold=False: calls.append(f"clear_{clear_hold}"),
    )

    asyncio.run(main_module.handle_selection_async(2))

    assert calls == ["clear_False"]
    assert selection_mode.is_selection_mode_active() is True

    selection_mode.exit_selection_mode()


def test_interactive_module_picker_ignores_empty_slots(monkeypatch):
    import app.selection_mode as selection_mode

    events = []

    class FakePrinter:
        def blip(self):
            events.append("blip")

        def reset_buffer(self, max_lines=0):  # noqa: ARG002
            events.append("reset_buffer")

        def print_header(self, *args, **kwargs):  # noqa: ARG002
            events.append("print_header")

        def print_line(self):
            events.append("print_line")

        def print_body(self, *args, **kwargs):  # noqa: ARG002
            events.append("print_body")

        def print_caption(self, *args, **kwargs):  # noqa: ARG002
            events.append("print_caption")

        def feed(self, lines=1):  # noqa: ARG002
            events.append("feed")

        def flush_buffer(self):
            events.append("flush_buffer")

    modules = {
        "adventure-one": ModuleInstance(
            id="adventure-one",
            type="adventure",
            name="Adventure One",
            config={},
        ),
        "adventure-two": ModuleInstance(
            id="adventure-two",
            type="adventure",
            name="Adventure Two",
            config={},
        ),
    }
    channels = {
        1: ChannelConfig(
            modules=[
                ChannelModuleAssignment(module_id="adventure-one", order=0),
                ChannelModuleAssignment(module_id="adventure-two", order=1),
            ]
        )
    }

    monkeypatch.setattr(main_module, "printer", FakePrinter())
    monkeypatch.setattr(
        main_module,
        "settings",
        types.SimpleNamespace(max_print_lines=200, channels=channels, modules=modules),
    )
    monkeypatch.setattr(
        main_module,
        "get_module",
        lambda module_type: types.SimpleNamespace(interactive=True),
        raising=False,
    )
    monkeypatch.setattr(main_module, "_clear_print_reservation", lambda clear_hold=False: None)

    selection_mode.exit_selection_mode()

    asyncio.run(main_module.trigger_channel(1))

    assert selection_mode.is_selection_mode_active() is True
    assert selection_mode.get_current_module_id() == "channel-menu-1"
    assert selection_mode.can_handle_selection(1) is True
    assert selection_mode.can_handle_selection(2) is True
    assert selection_mode.can_handle_selection(3) is False
    assert selection_mode.can_handle_selection(8) is True

    events.clear()
    asyncio.run(main_module.handle_selection_async(3))

    assert events == []
    assert selection_mode.is_selection_mode_active() is True

    selection_mode.exit_selection_mode()
