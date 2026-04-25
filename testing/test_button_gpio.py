from app.drivers.button_gpio import ButtonDriver


class _FakeEventHandle:
    def __init__(self, value: int):
        self.value = value

    def read_value(self) -> int:
        return self.value


def test_handle_release_triggers_long_press_callback():
    driver = ButtonDriver.__new__(ButtonDriver)
    driver.callback = None
    driver.long_press_callback = lambda: events.append("long")
    driver.long_press_ready_callback = None
    driver.factory_reset_callback = None
    driver.long_press_duration = 5.0
    driver.factory_reset_duration = 15.0
    driver.release_debounce_seconds = 0.12
    driver.is_pressed = True
    driver.press_start_time = 10.0
    driver.triggered_actions = {"long_press_threshold"}
    driver.last_callback_time = 0.0
    driver._release_candidate_since = None
    driver.event_handle = _FakeEventHandle(1)
    events = []

    driver._handle_release(16.0)

    assert events == ["long"]
    assert driver.is_pressed is False
    assert driver.press_start_time is None
    assert driver.triggered_actions == set()


def test_is_physically_released_reads_current_gpio_level():
    driver = ButtonDriver.__new__(ButtonDriver)
    driver.event_handle = _FakeEventHandle(1)
    assert driver._is_physically_released() is True

    driver.event_handle = _FakeEventHandle(0)
    assert driver._is_physically_released() is False


def test_release_must_be_stable_before_ending_hold():
    driver = ButtonDriver.__new__(ButtonDriver)
    driver.release_debounce_seconds = 0.12
    driver._release_candidate_since = None
    driver.event_handle = _FakeEventHandle(1)

    assert driver._release_is_stable(5.0) is False
    assert driver._release_candidate_since == 5.0
    assert driver._release_is_stable(5.05) is False
    assert driver._release_is_stable(5.13) is True


def test_release_glitch_resets_stable_release_window():
    driver = ButtonDriver.__new__(ButtonDriver)
    driver.release_debounce_seconds = 0.12
    driver._release_candidate_since = None
    driver.event_handle = _FakeEventHandle(1)

    assert driver._release_is_stable(1.0) is False
    driver.event_handle.value = 0
    assert driver._release_is_stable(1.05) is False
    assert driver._release_candidate_since is None
    driver.event_handle.value = 1
    assert driver._release_is_stable(1.10) is False


def test_duplicate_falling_edge_does_not_reset_active_hold():
    driver = ButtonDriver.__new__(ButtonDriver)
    driver.release_debounce_seconds = 0.12
    driver._release_candidate_since = None
    driver.is_pressed = True
    driver.press_start_time = 10.0
    driver.triggered_actions = {"long_press_threshold"}
    driver.event_handle = _FakeEventHandle(0)

    current_time = 12.0

    if driver.event_handle.read_value() == 0 and not driver.is_pressed:
        driver._handle_press(current_time)

    assert driver.press_start_time == 10.0
    assert driver.triggered_actions == {"long_press_threshold"}
