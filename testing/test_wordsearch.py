import pytest
from unittest.mock import MagicMock
from app.modules.wordsearch import (
    WordSearchGenerator, execute_wordsearch,
    DIR_RIGHT, DIR_DOWN, DIR_DOWN_RIGHT, DIR_UP_RIGHT,
    DIR_LEFT, DIR_UP, DIR_UP_LEFT, DIR_DOWN_LEFT
)

def test_wordsearch_generator_dimensions():
    """Verify word search initializes with non-square dimensions."""
    gen = WordSearchGenerator(12, 20)
    assert gen.width == 12
    assert gen.height == 20
    assert len(gen.grid) == 20
    assert len(gen.grid[0]) == 12

def test_wordsearch_placement_bounds():
    """Ensure words aren't placed outside the 12-column constraint."""
    gen = WordSearchGenerator(12, 12)
    # Horizontal fits exactly
    assert gen.can_place("TWELVELETTER", 0, 0, *DIR_RIGHT) is True
    # Horizontal overflows
    assert gen.can_place("TWELVELETTERS", 0, 0, *DIR_RIGHT) is False
    # Vertical fits (since height is 12)
    assert gen.can_place("TWELVELETTER", 0, 0, *DIR_DOWN) is True
    # Vertical overflows
    assert gen.can_place("TWELVELETTERS", 0, 0, *DIR_DOWN) is False

def test_wordsearch_vertical():
    gen = WordSearchGenerator(6, 6)
    word_pool = ["PYTHON"]
    # Force only vertical down
    directions = [DIR_DOWN]
    gen.generate(word_pool, 1, directions)

    assert any(p['word'] == "PYTHON" for p in gen.words_placed)
    
    # Verify word can be found vertically in the grid
    found = False
    
    for y in range(6):
        column_segment = ""
        for x in range(6):
            column_segment = column_segment + gen.grid[x][y]
            if "PYTHON" in column_segment:
                found = True
                break

    assert found, "PYTHON should be placed vertically in the grid"

def test_wordsearch_vertical_backwards():
    gen = WordSearchGenerator(6, 6)
    word_pool = ["PYTHON"]
    # Force only vertical backwards
    directions = [DIR_UP]
    gen.generate(word_pool, 1, directions)

    assert any(p['word'] == "PYTHON" for p in gen.words_placed)    
    found = False
    
    for y in range(6):
        column_segment = ""
        for x in range(6):
            column_segment = column_segment + gen.grid[x][y]
            if "NOHTYP" in column_segment:
                found = True
                break

    assert found, "PYTHON should be placed vertically in the grid spelled backwards"

def test_wordsearch_horizontal():
    gen = WordSearchGenerator(6, 6)
    word_pool = ["PYTHON"]
    # Force only horizontal right
    directions = [DIR_RIGHT]
    gen.generate(word_pool, 1, directions)

    assert any(p['word'] == "PYTHON" for p in gen.words_placed)

    # Verify word can be found horizontally in the grid
    found = False
    for x in range(6):
        row_segment = ""
        for y in range(6):
            row_segment = row_segment + gen.grid[x][y]
            if "PYTHON" in row_segment:
                found = True
                break

    assert found, "PYTHON should be placed horizontally in the grid"

def test_wordsearch_horizontal_backwards():
    gen = WordSearchGenerator(6, 6)
    word_pool = ["PYTHON"]
    # Force only horizontal backwards
    directions = [DIR_LEFT]
    gen.generate(word_pool, 1, directions)

    assert any(p['word'] == "PYTHON" for p in gen.words_placed)

    # Verify word can be found horizontally in the grid
    found = False
    for x in range(6):
        row_segment = ""
        for y in range(6):
            row_segment = row_segment + gen.grid[x][y]
            if "NOHTYP" in row_segment:
                found = True
                break

    assert found, "PYTHON should be placed horizontally in the grid spelled backwards"

def test_wordsearch_diagonal_left_to_right():
    gen = WordSearchGenerator(6, 6)
    word_pool = ["PYTHON"]
    # Force only diagonal left to right
    directions = [DIR_DOWN_RIGHT]
    gen.generate(word_pool, 1, directions)

    assert any(p['word'] == "PYTHON" for p in gen.words_placed)
    
    # P         (0,0)
    #  Y        (1,1)
    #   T       (2,2)
    #    H      (3,3)
    #     O     (4,4)
    #      N    (5,5)
    diagonal_segment = "".join([gen.grid[0][0], gen.grid[1][1], gen.grid[2][2], gen.grid[3][3], gen.grid[4][4], gen.grid[5][5]])
    assert "PYTHON" in diagonal_segment, "PYTHON should be placed diagonally in the grid left to right"

def test_wordsearch_diagonal_left_to_right_spelled_backwards():
    gen = WordSearchGenerator(6, 6)
    word_pool = ["PYTHON"]
    # Force only diagonal left to right
    directions = [DIR_UP_LEFT]
    gen.generate(word_pool, 1, directions)

    assert any(p['word'] == "PYTHON" for p in gen.words_placed)
    
    # N         (0,0)
    #  O        (1,1)
    #   H       (2,2)
    #    T      (3,3)
    #     Y     (4,4)
    #      P    (5,5)
    diagonal_segment = "".join([gen.grid[0][0], gen.grid[1][1], gen.grid[2][2], gen.grid[3][3], gen.grid[4][4], gen.grid[5][5]])
    assert "NOHTYP" in diagonal_segment, "PYTHON should be placed diagonally in the grid left to right spelled backwards"

def test_wordsearch_diagonal_right_to_left():
    gen = WordSearchGenerator(6, 6)
    word_pool = ["PYTHON"]
    # Force only diagonal right to left
    directions = [DIR_DOWN_LEFT]
    gen.generate(word_pool, 1, directions)

    assert any(p['word'] == "PYTHON" for p in gen.words_placed)

    #     P (0,5)
    #    Y  (1,4)
    #   T   (2,3)
    #  H    (3,2)
    # O     (4,1)
    #N      (5,0)
    diagonal_segment = "".join([gen.grid[0][5], gen.grid[1][4], gen.grid[2][3], gen.grid[3][2], gen.grid[4][1], gen.grid[5][0]])
    assert "PYTHON" in diagonal_segment, "PYTHON should be placed diagonally in the grid right to left"

def test_wordsearch_diagonal_right_to_left_spelled_backwards():
    gen = WordSearchGenerator(6, 6)
    word_pool = ["PYTHON"]
    # Force only diagonal right to left
    directions = [DIR_UP_RIGHT]
    gen.generate(word_pool, 1, directions)

    assert any(p['word'] == "PYTHON" for p in gen.words_placed)

    #     N (0,5)
    #    O  (1,4)
    #   H   (2,3)
    #  T    (3,2)
    # Y     (4,1)
    #P      (5,0)
    diagonal_segment = "".join([gen.grid[0][5], gen.grid[1][4], gen.grid[2][3], gen.grid[3][2], gen.grid[4][1], gen.grid[5][0]])
    assert "NOHTYP" in diagonal_segment, "PYTHON should be placed diagonally in the grid right to left spelled backwards"

def test_wordsearch_overlap_logic():
    gen = WordSearchGenerator(10, 10)
    # Place two words that overlap
    gen.place("APPLE", 0, 0, *DIR_RIGHT)
    gen.place("PLUM", 2, 0, *DIR_DOWN)
    # A P P L E
    #   P
    #   L
    #   U
    #   M
    assert gen._calculate_overlap() == pytest.approx(1/9) # 1 shared cell out of 9 total cells

    gen = WordSearchGenerator(10, 10)
    gen.place("CAT", 0, 0, *DIR_RIGHT)
    gen.place("DOG", 0, 2, *DIR_RIGHT)
    assert gen._calculate_overlap() == 0.0 # No overlap

    gen = WordSearchGenerator(10, 10)
    gen.place("TEST", 0, 0, *DIR_RIGHT)
    gen.place("BEST", 0, 0, *DIR_DOWN) # Overlap at 'T'
    assert gen._calculate_overlap() == pytest.approx(1/8) # 1 shared cell out of 8 total cells

    gen = WordSearchGenerator(10, 10)
    gen.place("A", 0, 0, *DIR_RIGHT)
    gen.place("B", 2, 2, *DIR_RIGHT)
    gen.place("C", 4, 4, *DIR_RIGHT)
    assert gen._calculate_overlap() == 0.0 # No overlap