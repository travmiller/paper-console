import random
from typing import Dict, Any


class SudokuGenerator:
    def __init__(self):
        self.grid = [[0 for _ in range(9)] for _ in range(9)]

    def is_valid(self, grid, row, col, num):
        """Checks if placing num at grid[row][col] is valid."""
        # Check Row
        for x in range(9):
            if grid[row][x] == num:
                return False

        # Check Column
        for x in range(9):
            if grid[x][col] == num:
                return False

        # Check 3x3 Box
        start_row = row - row % 3
        start_col = col - col % 3
        for i in range(3):
            for j in range(3):
                if grid[i + start_row][j + start_col] == num:
                    return False
        return True

    def solve(self, grid):
        """Solves the grid using backtracking. Returns True if solved."""
        for i in range(9):
            for j in range(9):
                if grid[i][j] == 0:
                    for num in range(1, 10):
                        if self.is_valid(grid, i, j, num):
                            grid[i][j] = num
                            if self.solve(grid):
                                return True
                            grid[i][j] = 0
                    return False
        return True

    def generate_full_board(self):
        """Generates a completely filled valid Sudoku board."""
        self.grid = [[0 for _ in range(9)] for _ in range(9)]

        # Fill diagonal 3x3 matrices first (independent of each other)
        for i in range(0, 9, 3):
            self.fill_box(i, i)

        # Solve the rest to fill the board
        self.solve(self.grid)

    def fill_box(self, row, col):
        """Fills a 3x3 box with random 1-9."""
        num = 0
        for i in range(3):
            for j in range(3):
                while True:
                    num = random.randint(1, 9)
                    if not self.used_in_box(row, col, num):
                        break
                self.grid[row + i][col + j] = num

    def used_in_box(self, row_start, col_start, num):
        for i in range(3):
            for j in range(3):
                if self.grid[row_start + i][col_start + j] == num:
                    return True
        return False

    def remove_digits(self, count=40):
        """Removes 'count' digits to create the puzzle."""
        # Note: A true Sudoku generator checks for uniqueness of solution.
        # For a V1 toy, random removal is usually "good enough" but technically imperfect.
        attempts = count
        while attempts > 0:
            row = random.randint(0, 8)
            col = random.randint(0, 8)
            if self.grid[row][col] != 0:
                self.grid[row][col] = 0
                attempts -= 1


def generate_puzzle(difficulty="medium"):
    """Generates a puzzle grid."""
    gen = SudokuGenerator()
    gen.generate_full_board()

    # Simple difficulty mapping
    remove_count = 30
    if difficulty == "hard":
        remove_count = 50
    elif difficulty == "medium":
        remove_count = 40

    gen.remove_digits(remove_count)
    return gen.grid


def format_sudoku_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints a Sudoku puzzle."""

    # Default Difficulty
    difficulty = "medium"
    if config and "difficulty" in config:
        difficulty = config["difficulty"]

    from datetime import datetime

    grid = generate_puzzle(difficulty)

    printer.print_header(module_name or "SUDOKU", icon="grid-nine")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    printer.print_subheader(f"Difficulty: {difficulty.title()}")
    printer.print_line()

    # Render grid as full width (384 dots - 4px borders) / 9 cells = ~42px per cell
    printer_width_dots = getattr(printer, 'PRINTER_WIDTH_DOTS', 384)
    cell_size = (printer_width_dots - 4) // 9  # -4 for 2px borders on each side
    printer.print_sudoku(grid, cell_size=cell_size)
    
    printer.print_line()
    printer.print_caption("Good luck!")
