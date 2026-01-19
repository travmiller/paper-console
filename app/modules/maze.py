import random
from typing import Dict, Any, List, Tuple

class MazeGenerator:
    def __init__(self, width: int = 15, height: int = 15):
        # Ensure dimensions are odd for wall/path representation
        self.width = width if width % 2 != 0 else width + 1
        self.height = height if height % 2 != 0 else height + 1
        self.grid = [[1 for _ in range(self.width)] for _ in range(self.height)]
        # 1 = Wall, 0 = Path

    def generate(self):
        """Generates a maze using recursive backtracking."""
        # Start at (1, 1)
        start_x, start_y = 1, 1
        self.grid[start_y][start_x] = 0
        
        stack = [(start_x, start_y)]
        
        while stack:
            x, y = stack[-1]
            neighbors = self._get_unvisited_neighbors(x, y)
            
            if neighbors:
                nx, ny = random.choice(neighbors)
                # Remove wall between current and neighbor
                mid_x = (x + nx) // 2
                mid_y = (y + ny) // 2
                self.grid[mid_y][mid_x] = 0
                self.grid[ny][nx] = 0
                stack.append((nx, ny))
            else:
                stack.pop()
        
        # Randomize entrance and exit positions (must be odd to align with paths)
        valid_positions = [x for x in range(1, self.width - 1) if x % 2 == 1]
        entrance_x = random.choice(valid_positions)
        exit_x = random.choice(valid_positions)
        self.grid[0][entrance_x] = 0  # Entrance (top, random position)
        self.grid[self.height - 1][exit_x] = 0  # Exit (bottom, random position)

    def _get_unvisited_neighbors(self, x, y) -> List[Tuple[int, int]]:
        directions = [
            (0, -2), # North
            (0, 2),  # South
            (-2, 0), # West
            (2, 0)   # East
        ]
        neighbors = []
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 < nx < self.width - 1 and 0 < ny < self.height - 1:
                if self.grid[ny][nx] == 1:
                    neighbors.append((nx, ny))
        return neighbors

def format_maze_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Prints a Maze puzzle."""
    from datetime import datetime
    
    # Fixed size for thermal printer (61x61 for maximum challenge)
    width, height = 61, 61
    
    # Generate Maze
    maze = MazeGenerator(width, height)
    maze.generate()
    
    # Header
    printer.print_header(module_name or "MAZE", icon="path")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    printer.print_subheader("START ↑  ·  END ↓")
    printer.print_line()
    
    # Print maze as full width (384 dots / 15 cells = ~25px per cell)
    # Use printer's width in dots (384 for 58mm thermal printer)
    printer_width_dots = getattr(printer, 'PRINTER_WIDTH_DOTS', 384)
    cell_size = printer_width_dots // width
    printer.print_maze(maze.grid, cell_size=cell_size)
    
    printer.print_line()
    printer.print_caption("Find the path!")

