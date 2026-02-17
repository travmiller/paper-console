"""Moon phase rendering regression tests."""

from app.modules.astronomy import draw_moon_phase_image


def _lit_fraction_in_disc(phase_value: float, size: int = 64) -> float:
    image = draw_moon_phase_image(phase_value, size)
    pixels = image.load()

    center_x = size // 2
    center_y = size // 2
    radius = max(2, (size // 2) - 2)

    lit_pixels = 0
    total_pixels = 0
    for py in range(size):
        for px in range(size):
            dx = px - center_x
            dy = py - center_y
            if dx * dx + dy * dy > radius * radius:
                continue

            total_pixels += 1
            lit_pixels += 1 if pixels[px, py] else 0

    return lit_pixels / total_pixels if total_pixels else 0.0


def _lit_centroid_x(phase_value: float, size: int = 64) -> float:
    image = draw_moon_phase_image(phase_value, size)
    pixels = image.load()

    center_x = size // 2
    center_y = size // 2
    radius = max(2, (size // 2) - 2)

    lit_count = 0
    x_sum = 0.0
    for py in range(size):
        for px in range(size):
            dx = px - center_x
            dy = py - center_y
            if dx * dx + dy * dy > radius * radius:
                continue

            if pixels[px, py]:
                lit_count += 1
                x_sum += dx / radius

    return x_sum / lit_count if lit_count else 0.0


def test_new_moon_is_mostly_dark():
    new_lit = _lit_fraction_in_disc(0.0)
    full_lit = _lit_fraction_in_disc(14.0)
    assert new_lit < 0.40
    assert full_lit - new_lit > 0.50


def test_full_moon_is_mostly_lit():
    assert _lit_fraction_in_disc(14.0) > 0.85


def test_quarter_moons_are_near_half_lit():
    new_lit = _lit_fraction_in_disc(0.0)
    full_lit = _lit_fraction_in_disc(14.0)
    first_quarter_lit = _lit_fraction_in_disc(7.0)
    last_quarter_lit = _lit_fraction_in_disc(21.0)

    assert 0.50 <= first_quarter_lit <= 0.72
    assert 0.50 <= last_quarter_lit <= 0.72
    assert new_lit < first_quarter_lit < full_lit
    assert new_lit < last_quarter_lit < full_lit


def test_waxing_and_waning_sides_are_distinct():
    assert _lit_centroid_x(7.0) > 0.15
    assert _lit_centroid_x(21.0) < -0.15
