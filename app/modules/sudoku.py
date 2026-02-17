import random
from typing import Dict, Any, List
from PIL import Image, ImageDraw
from app.module_registry import register_module


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

    def count_solutions(self, grid, limit=2):
        """Counts solutions up to 'limit'. Returns count (0, 1, or 2+)."""
        count = [0]  # Use list to allow modification in nested function
        
        def solve_count(g):
            if count[0] >= limit:
                return
            for i in range(9):
                for j in range(9):
                    if g[i][j] == 0:
                        for num in range(1, 10):
                            if self.is_valid(g, i, j, num):
                                g[i][j] = num
                                solve_count(g)
                                g[i][j] = 0
                                if count[0] >= limit:
                                    return
                        return
            count[0] += 1
        
        # Work on a copy to avoid modifying original
        grid_copy = [row[:] for row in grid]
        solve_count(grid_copy)
        return count[0]

    def remove_digits(self, count=40):
        """Removes digits while ensuring unique solution."""
        # Get all filled cells and shuffle them
        cells = [(r, c) for r in range(9) for c in range(9) if self.grid[r][c] != 0]
        random.shuffle(cells)
        
        removed = 0
        for row, col in cells:
            if removed >= count:
                break
            
            # Tentatively remove the digit
            backup = self.grid[row][col]
            self.grid[row][col] = 0
            
            # Check if puzzle still has exactly one solution
            if self.count_solutions(self.grid, limit=2) != 1:
                # Not unique, restore the digit
                self.grid[row][col] = backup
            else:
                removed += 1


def generate_puzzle(difficulty="medium"):
    """Generates a puzzle grid."""
    gen = SudokuGenerator()
    gen.generate_full_board()

    # Simple difficulty mapping
    remove_count = 20
    if difficulty.lower() == "hard":
        remove_count = 50
    elif difficulty.lower() == "medium":
        remove_count = 40
    elif difficulty.lower() == "easy":
        remove_count = 20

    gen.remove_digits(remove_count)
    return gen.grid


def draw_sudoku_image(grid: List[List[int]], cell_size: int, font) -> Image.Image:
    """Draw a Sudoku grid as a bitmap image.

    Args:
        grid: 9x9 grid where 0 = empty, 1-9 = number
        cell_size: Size of each cell in pixels
        font: Font for drawing numbers
    """
    border_width = 2  # Thick border for outer edges
    thin_width = 1  # Thin border for inner cells

    total_size = 9 * cell_size + 2 * border_width
    
    # Create white image (1-bit monochrome)
    image = Image.new("1", (total_size, total_size), 1)
    draw = ImageDraw.Draw(image)

    # Draw outer border
    draw.rectangle(
        [0, 0, total_size - 1, total_size - 1], outline=0, width=border_width
    )

    # Draw grid lines and numbers
    for row in range(9):
        for col in range(9):
            cell_x = border_width + col * cell_size
            cell_y = border_width + row * cell_size

            # Determine boundary widths (thick for 3x3 boundaries)
            top_width = border_width if row % 3 == 0 else thin_width
            left_width = border_width if col % 3 == 0 else thin_width
            
            # Draw cell borders
            # Top
            if row % 3 == 0 and row > 0:
                 draw.line(
                    [cell_x, cell_y, cell_x + cell_size, cell_y],
                    fill=0,
                    width=top_width,
                )
            # Left
            if col % 3 == 0 and col > 0:
                draw.line(
                    [cell_x, cell_y, cell_x, cell_y + cell_size],
                    fill=0,
                    width=left_width,
                )
            # Right (always draw thin, thick handled by next col's left or outer border)
            draw.line(
                [cell_x + cell_size, cell_y, cell_x + cell_size, cell_y + cell_size],
                fill=0,
                width=thin_width,
            )
            # Bottom (always draw thin, thick handled by next row's top or outer border)
            draw.line(
                [cell_x, cell_y + cell_size, cell_x + cell_size, cell_y + cell_size],
                fill=0,
                width=thin_width,
            )

            # Draw number if present
            value = grid[row][col]
            if value != 0:
                num_str = str(value)
                # Center text in cell
                if font:
                    bbox = font.getbbox(num_str)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                else:
                    text_width = cell_size // 2
                    text_height = cell_size // 2

                text_x = cell_x + (cell_size - text_width) // 2
                text_y = cell_y + (cell_size - text_height) // 2

                if font:
                    draw.text((text_x, text_y), num_str, font=font, fill=0)
                else:
                    draw.text((text_x, text_y), num_str, fill=0)

    return image


@register_module(
    type_id="games",
    label="Sudoku",
    description="Generate printable Sudoku puzzles in medium or hard difficulty",
    icon="grid-nine",
    offline=True,
    category="games",
    config_schema={
        "type": "object",
        "properties": {
             "difficulty": {
                 "type": "string", 
                 "title": "Difficulty", 
                 "enum": ["Easy", "Medium", "Hard"], 
                 "default": "Easy"
             }
        }
    }
)
def format_sudoku_receipt(
    printer, config: Dict[str, Any] = None, module_name: str = None
):
    """Prints a Sudoku puzzle."""

    # Default Difficulty
    difficulty = "Easy"
    if config and "difficulty" in config:
        difficulty = config["difficulty"]

    from datetime import datetime

    grid = generate_puzzle(difficulty)

    printer.print_header(module_name or "SUDOKU", icon="grid-nine")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_subheader(f"Difficulty: {difficulty.title()}")

    # Render grid as full width (384 dots - 4px borders) / 9 cells = ~42px per cell
    printer_width_dots = getattr(printer, 'PRINTER_WIDTH_DOTS', 384)
    cell_size = (printer_width_dots - 4) // 9  # -4 for 2px borders on each side
    
    # Get bold font for numbers (if available)
    font = getattr(printer, "_get_font", lambda s: None)("bold")

    # Generate image and print
    sudoku_image = draw_sudoku_image(grid, cell_size, font)
    printer.print_image(sudoku_image)
