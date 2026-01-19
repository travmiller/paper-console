import random
from typing import Dict, Any, List, Tuple


class MazeGenerator:
    """
    Enhanced maze generator using Hunt-and-Kill algorithm with post-processing
    for loops and extended dead-ends. Creates challenging, winding mazes.
    """
    
    def __init__(self, width: int = 61, height: int = 61):
        # Ensure dimensions are odd for wall/path representation
        self.width = width if width % 2 != 0 else width + 1
        self.height = height if height % 2 != 0 else height + 1
        self.grid = [[1 for _ in range(self.width)] for _ in range(self.height)]
        # 1 = Wall, 0 = Path
        self.entrance_x = None
        self.exit_x = None

    def generate(self):
        """Generates a maze using Hunt-and-Kill algorithm with enhancements."""
        # Phase 1: Hunt-and-Kill base maze generation
        self._hunt_and_kill()
        
        # Phase 2: Add loops by removing some internal walls (~5%)
        self._add_loops(loop_percentage=0.05)
        
        # Phase 3: Extend dead-ends to make wrong turns more costly
        self._extend_dead_ends()
        
        # Phase 4: Set randomized entrance and exit
        self._set_entrance_exit()

    def _hunt_and_kill(self):
        """
        Hunt-and-Kill algorithm: Creates mazes with longer corridors.
        Walk phase: Random walk carving passages.
        Hunt phase: Scan grid to find unvisited cell adjacent to visited cell.
        """
        # Start from bottom-right area to bias longer paths to top-left entrance
        start_x = self.width - 2 if (self.width - 2) % 2 == 1 else self.width - 3
        start_y = self.height - 2 if (self.height - 2) % 2 == 1 else self.height - 3
        
        current = (start_x, start_y)
        self.grid[current[1]][current[0]] = 0
        
        while current:
            # Walk phase: random walk from current position
            current = self._walk(current)
            
            if current is None:
                # Hunt phase: find unvisited cell adjacent to visited
                current = self._hunt()

    def _walk(self, start: Tuple[int, int]) -> Tuple[int, int] | None:
        """Random walk, carving passages until stuck."""
        x, y = start
        
        while True:
            neighbors = self._get_unvisited_neighbors(x, y)
            
            if not neighbors:
                return None  # Stuck, need to hunt
            
            # Choose random neighbor
            nx, ny = random.choice(neighbors)
            
            # Carve passage
            mid_x = (x + nx) // 2
            mid_y = (y + ny) // 2
            self.grid[mid_y][mid_x] = 0
            self.grid[ny][nx] = 0
            
            x, y = nx, ny
        
        return None

    def _hunt(self) -> Tuple[int, int] | None:
        """Scan grid for unvisited cell adjacent to visited cell."""
        # Scan from top-left to bias path generation toward entrance
        for y in range(1, self.height - 1, 2):
            for x in range(1, self.width - 1, 2):
                if self.grid[y][x] == 1:  # Unvisited
                    # Check for visited neighbors
                    visited_neighbors = self._get_visited_neighbors(x, y)
                    if visited_neighbors:
                        # Connect to a random visited neighbor
                        vx, vy = random.choice(visited_neighbors)
                        mid_x = (x + vx) // 2
                        mid_y = (y + vy) // 2
                        self.grid[mid_y][mid_x] = 0
                        self.grid[y][x] = 0
                        return (x, y)
        return None

    def _get_unvisited_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Get unvisited (wall) neighbors 2 cells away."""
        directions = [(0, -2), (0, 2), (-2, 0), (2, 0)]
        neighbors = []
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 < nx < self.width - 1 and 0 < ny < self.height - 1:
                if self.grid[ny][nx] == 1:
                    neighbors.append((nx, ny))
        return neighbors

    def _get_visited_neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Get visited (path) neighbors 2 cells away."""
        directions = [(0, -2), (0, 2), (-2, 0), (2, 0)]
        neighbors = []
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if 0 < nx < self.width - 1 and 0 < ny < self.height - 1:
                if self.grid[ny][nx] == 0:
                    neighbors.append((nx, ny))
        return neighbors

    def _add_loops(self, loop_percentage: float = 0.05):
        """
        Remove random internal walls to create loops.
        This breaks the wall-follower solving strategy.
        """
        # Find all internal walls that could be removed (between two path cells)
        removable_walls = []
        
        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                if self.grid[y][x] == 1:  # Wall
                    # Check if removing this wall would connect two paths
                    # Horizontal connection
                    if x > 0 and x < self.width - 1:
                        if self.grid[y][x-1] == 0 and self.grid[y][x+1] == 0:
                            removable_walls.append((x, y))
                            continue
                    # Vertical connection
                    if y > 0 and y < self.height - 1:
                        if self.grid[y-1][x] == 0 and self.grid[y+1][x] == 0:
                            removable_walls.append((x, y))
        
        # Remove a percentage of these walls
        num_to_remove = int(len(removable_walls) * loop_percentage)
        walls_to_remove = random.sample(removable_walls, min(num_to_remove, len(removable_walls)))
        
        for x, y in walls_to_remove:
            self.grid[y][x] = 0

    def _extend_dead_ends(self):
        """
        Find dead-ends and extend them where possible.
        Makes wrong turns more costly by increasing dead-end length.
        """
        # Find all dead-ends (path cells with only one open neighbor)
        dead_ends = []
        
        for y in range(1, self.height - 1, 2):
            for x in range(1, self.width - 1, 2):
                if self.grid[y][x] == 0:
                    open_neighbors = self._count_open_neighbors(x, y)
                    if open_neighbors == 1:
                        dead_ends.append((x, y))
        
        # Try to extend each dead-end
        for x, y in dead_ends:
            self._try_extend_dead_end(x, y)

    def _count_open_neighbors(self, x: int, y: int) -> int:
        """Count adjacent path cells (1 cell away, not 2)."""
        count = 0
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if self.grid[ny][nx] == 0:
                    count += 1
        return count

    def _try_extend_dead_end(self, x: int, y: int):
        """Try to extend a dead-end by 1-2 cells in a random direction."""
        directions = [(0, -2), (0, 2), (-2, 0), (2, 0)]
        random.shuffle(directions)
        
        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            mid_x, mid_y = x + dx // 2, y + dy // 2
            
            # Check if we can extend (target must be wall and in bounds)
            if 0 < nx < self.width - 1 and 0 < ny < self.height - 1:
                if self.grid[ny][nx] == 1 and self.grid[mid_y][mid_x] == 1:
                    # Extend the dead-end
                    self.grid[mid_y][mid_x] = 0
                    self.grid[ny][nx] = 0
                    
                    # 50% chance to extend one more cell
                    if random.random() < 0.5:
                        nnx, nny = nx + dx, ny + dy
                        nmid_x, nmid_y = nx + dx // 2, ny + dy // 2
                        if 0 < nnx < self.width - 1 and 0 < nny < self.height - 1:
                            if self.grid[nny][nnx] == 1 and self.grid[nmid_y][nmid_x] == 1:
                                self.grid[nmid_y][nmid_x] = 0
                                self.grid[nny][nnx] = 0
                    return

    def _set_entrance_exit(self):
        """Set randomized entrance (top) and exit (bottom) positions."""
        valid_positions = [x for x in range(1, self.width - 1) if x % 2 == 1]
        self.entrance_x = random.choice(valid_positions)
        self.exit_x = random.choice(valid_positions)
        self.grid[0][self.entrance_x] = 0  # Entrance (top)
        self.grid[self.height - 1][self.exit_x] = 0  # Exit (bottom)


def format_maze_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Prints a challenging Maze puzzle."""
    from datetime import datetime
    
    # Fixed size for thermal printer (61x61 for maximum challenge)
    width, height = 61, 61
    
    # Generate enhanced Maze
    maze = MazeGenerator(width, height)
    maze.generate()
    
    # Header
    printer.print_header(module_name or "MAZE", icon="path")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    printer.print_subheader("START ↑  ·  END ↓")
    printer.print_line()
    
    # Print maze as full width
    # Use printer's width in dots (384 for 58mm thermal printer)
    printer_width_dots = getattr(printer, 'PRINTER_WIDTH_DOTS', 384)
    cell_size = printer_width_dots // width
    printer.print_maze(maze.grid, cell_size=cell_size)
    
    printer.print_line()
    printer.print_caption("Find the path!")
