import csv
import random
import os
import logging
from typing import List, Dict, Tuple, Optional, Any
import string
from PIL import Image, ImageDraw, ImageFont
from app.module_registry import register_module
from app.config import format_print_datetime

logger = logging.getLogger(__name__)

GRID_WIDTH = 8

class CrosswordGenerator:
    def __init__(self, width: int, initial_height: int):
        self.width = width
        self.height = initial_height # Initial height, will grow if needed
        self.grid = [[' ' for _ in range(width)] for _ in range(initial_height)]
        self.words_placed = []  # List of (word, hint, x, y, direction, number)

    def can_place(self, word: str, x: int, y: int, direction: str) -> bool:
        if x < 0 or y < 0: return False
        if direction == "across":
            if x + len(word) > self.width or y >= self.height: return False
            for i, char in enumerate(word):
                current = self.grid[y][x + i]
                if current != ' ' and current != char: return False
                # Check for adjacent letters to avoid creating new invalid words
                if current == ' ':
                    if (y > 0 and self.grid[y-1][x+i] != ' ') or \
                       (y < self.height - 1 and self.grid[y+1][x+i] != ' '):
                        return False
            # Check start/end neighbors
            if x > 0 and self.grid[y][x-1] != ' ': return False
            if x + len(word) < self.width and self.grid[y][x+len(word)] != ' ': return False
        else:  # "down"
            if y + len(word) > self.height or x >= self.width: return False
            for i, char in enumerate(word):
                current = self.grid[y + i][x]
                if current != ' ' and current != char: return False
                if current == ' ':
                    if (x > 0 and self.grid[y+i][x-1] != ' ') or \
                       (x < self.width - 1 and self.grid[y+i][x+1] != ' '):
                        return False
            if y > 0 and self.grid[y-1][x] != ' ': return False
            if y + len(word) < self.height and self.grid[y+len(word)][x] != ' ': return False
        return True

    def place(self, word: str, hint: str, x: int, y: int, direction: str, number: int):
        for i, char in enumerate(word):
            if direction == "across":
                self.grid[y][x + i] = char
            else:
                self.grid[y + i][x] = char
        self.words_placed.append({'word': word, 'hint': hint, 'x': x, 'y': y, 'dir': direction, 'num': number})

    def _calculate_overlap(self) -> float:
        """Calculates the percentage of placed words that overlap with at least one other word."""
        if len(self.words_placed) < 2: return 0.0
        
        occupied_cells = set()
        word_cells = {} # {word_index: set_of_cells}

        for idx, placement in enumerate(self.words_placed):
            current_word_cells = set()
            for k in range(len(placement['word'])):
                if placement['dir'] == "across":
                    cell = (placement['x'] + k, placement['y'])
                else:
                    cell = (placement['x'], placement['y'] + k)
                occupied_cells.add(cell)
                current_word_cells.add(cell)
            word_cells[idx] = current_word_cells

        total_word_length = sum(len(p['word']) for p in self.words_placed)
        if total_word_length == 0: return 0.0

        # Count actual overlaps
        overlap_count = 0
        for i in range(len(self.words_placed)):
            for j in range(i + 1, len(self.words_placed)):
                overlap_count += len(word_cells[i].intersection(word_cells[j]))

        unique_cells = len(occupied_cells)
        return (total_word_length - unique_cells) / total_word_length

    def _calculate_puzzle_score(self, num_words_placed: int, overlap_percentage: float, grid_height: int) -> float:
        """
        Calculates a score for the puzzle based on words placed, overlap, and grid size.
        Prioritizes more words, higher overlap, and smaller grid height.
        """
        # Scale factors
        score = (num_words_placed * 1000) + (overlap_percentage * 500) - (grid_height * 10)
        return score

    def generate(self, word_pool: List[Tuple[str, str]], num_words: int):
        # Sort word_pool by length descending to prioritize placing longer words first
        word_pool.sort(key=lambda x: len(x[0]), reverse=True)
        
        max_grid_height = self.width * 4 # Allow height to grow up to 4 times the width
        best_grid = None
        best_words_placed = []
        best_score = -1.0
        best_height = self.height

        # Growth loop: increase height if words don't fit
        current_height_attempt = self.width # Start with height equal to width
        
        while current_height_attempt <= max_grid_height:
            # Pre-calculate the grid and properties for this height level
            current_height_grid = [[' ' for _ in range(self.width)] for _ in range(current_height_attempt)]
            placed_all_at_this_height = False
            
            # Multiple attempts per height to maximize overlap and find good layouts
            for attempt in range(40): # 40 attempts as requested
                # Temporary instance state for this attempt
                self.grid = [row[:] for row in current_height_grid]
                self.words_placed = []
                self.height = current_height_attempt
                
                # Create a pool of words to try placing for this attempt.
                # Try to place more words than the target `num_words` to give more options,
                # as some words might be difficult to place.
                # Cap the consideration pool to avoid excessive computation.
                words_to_consider_for_placement = list(word_pool)
                random.shuffle(words_to_consider_for_placement)
                # Consider up to 2x the target number of words, or all available if fewer.
                words_to_consider_for_placement = words_to_consider_for_placement[:min(len(word_pool), num_words * 2)]
                
                # Keep track of words successfully placed in this attempt (by their original tuple)
                placed_words_in_this_attempt_set = set()

                # 1. Place the first word (seed) from the consideration pool
                if words_to_consider_for_placement:
                    first_word_tuple = words_to_consider_for_placement.pop(0)
                    first_word, first_hint = first_word_tuple
                    # Try to place in the center
                    start_x = (self.width - len(first_word)) // 2
                    start_y = current_height_attempt // 2
                    
                    if start_x >= 0 and self.can_place(first_word, start_x, start_y, "across"):
                        self.place(first_word, first_hint, start_x, start_y, "across", 0) # Number will be finalized later
                        placed_words_in_this_attempt_set.add(first_word_tuple)
                    elif len(first_word) <= current_height_attempt: # Try down if across fails or doesn't fit
                        start_x = self.width // 2
                        start_y = (current_height_attempt - len(first_word)) // 2
                        if start_y >= 0 and self.can_place(first_word, start_x, start_y, "down"):
                            self.place(first_word, first_hint, start_x, start_y, "down", 0)
                            placed_words_in_this_attempt_set.add(first_word_tuple)
                
                # 2. Try to place remaining words by intersection
                # Iterate over the remaining words in the consideration pool,
                # prioritizing those not yet placed.
                # We'll re-shuffle the remaining words to introduce more randomness for intersection attempts.
                remaining_words_to_try = [w_tuple for w_tuple in words_to_consider_for_placement if w_tuple not in placed_words_in_this_attempt_set]
                random.shuffle(remaining_words_to_try)

                for word_tuple in remaining_words_to_try:
                    word, hint = word_tuple

                    # Try to find an intersection point with an already placed word
                    possible_placements = []
                    for placed_word_info in self.words_placed:
                        for i, char_placed in enumerate(placed_word_info['word']):
                            for j, char_current in enumerate(word):
                                if char_placed == char_current:
                                    # Calculate potential start position for the current word
                                    if placed_word_info['dir'] == "across":
                                        # Current word will go down
                                        nx = placed_word_info['x'] + i
                                        ny = placed_word_info['y'] - j
                                        new_dir = "down"
                                    else:
                                        # Current word will go across
                                        nx = placed_word_info['x'] - j
                                        ny = placed_word_info['y'] + i
                                        new_dir = "across"

                                    if nx >= 0 and ny >= 0 and self.can_place(word, nx, ny, new_dir):
                                        # Count how many characters overlap with this specific placement
                                        intersections = 0
                                        for k, char in enumerate(word):
                                            tx, ty = (nx + k, ny) if new_dir == "across" else (nx, ny + k)
                                            if self.grid[ty][tx] == char:
                                                intersections += 1
                                        possible_placements.append((nx, ny, new_dir, intersections))
                    
                    if possible_placements:
                        # Prioritize placements with the most intersections
                        # Use distance to center as a tie-breaker for better density
                        center_x, center_y = self.width // 2, self.height // 2
                        possible_placements.sort(key=lambda p: (p[3], -(abs(p[0] - center_x) + abs(p[1] - center_y))), reverse=True)
                        
                        px, py, pdir, _ = possible_placements[0]
                        self.place(word, hint, px, py, pdir, 0)
                        placed_words_in_this_attempt_set.add(word_tuple)
                
                current_overlap = self._calculate_overlap()
                current_score = self._calculate_puzzle_score(len(self.words_placed), current_overlap, self.height)

                if len(self.words_placed) == num_words:
                    placed_all_at_this_height = True

                if current_score > best_score:
                    best_score = current_score
                    best_grid = [row[:] for row in self.grid]
                    best_words_placed = list(self.words_placed)
                    best_height = self.height
                    logger.debug(f"H={self.height}, Attempt={attempt}: New best score {best_score:.2f} with {len(best_words_placed)} words.")
            
            if placed_all_at_this_height:
                break # All words placed at this height, no need to grow further
            
            current_height_attempt += 1 # Increment height for next iteration
            logger.debug(f"Growing crossword grid to height {current_height_attempt}")

        # After all attempts, apply the best found puzzle
        if best_grid is not None:
            self.grid = best_grid
            self.words_placed = best_words_placed
            self.height = best_height
            logger.info(f"Final crossword generated with height {self.height}, {len(self.words_placed)} words, score {best_score:.2f}")
        else:
            logger.warning(f"Could not generate a satisfactory crossword after growing to height {max_grid_height}.")
            # Fallback to an empty grid or a minimal one if nothing was placed
            self.grid = [[' ' for _ in range(self.width)] for _ in range(self.width)] # Reset to initial height
            self.words_placed = []
            self.height = self.width

        self.finalize_numbers()

    def finalize_numbers(self):
        # Identify cells that start a word
        starters = {}
        for wp in self.words_placed:
            pos = (wp['x'], wp['y'])
            if pos not in starters:
                starters[pos] = []
            starters[pos].append(wp)
            
        # Sort positions to assign numbers in order
        sorted_pos = sorted(starters.keys(), key=lambda p: (p[1], p[0]))
        
        final_words = []
        for i, pos in enumerate(sorted_pos, 1):
            for wp in starters[pos]:
                wp['num'] = i
                final_words.append(wp)
        self.words_placed = final_words

def render_crossword_grid(generator: CrosswordGenerator, cell_size: int, font_path: str = None) -> Image.Image:
    """Renders the crossword grid as a 1-bit bitmap."""
    # Calculate used bounds to crop empty space
    min_y = generator.height
    max_y = 0
    for wp in generator.words_placed:
        min_y = min(min_y, wp['y'])
        h = len(wp['word']) if wp['dir'] == "down" else 1
        max_y = max(max_y, wp['y'] + h)
    
    # Add 1 row margin
    start_y = max(0, min_y - 1)
    end_y = min(generator.height, max_y + 1)
    used_rows = end_y - start_y

    img_w = generator.width * cell_size + 2
    img_h = used_rows * cell_size + 2
    
    # Start with a black image (0 = black) to form the blocks and grid lines
    img = Image.new("1", (img_w, img_h), 0)
    draw = ImageDraw.Draw(img)
    
    # Load a small font for numbers
    try:
        num_font = ImageFont.truetype(font_path, max(8, cell_size // 3)) if font_path else ImageFont.load_default()
    except:
        num_font = ImageFont.load_default()

    # Draw white squares for letters
    for y in range(start_y, end_y):
        for x in range(generator.width):
            if generator.grid[y][x] != ' ':
                # Draw white inset (1 = white)
                # This leaves a black border around each white square
                x0 = x * cell_size + 2
                y0 = (y - start_y) * cell_size + 2
                x1 = (x + 1) * cell_size - 1
                y1 = (y - start_y + 1) * cell_size - 1
                draw.rectangle([x0, y0, x1, y1], fill=1)

    # Draw numbers
    # We need to know which cells have a number
    num_map = {}
    for wp in generator.words_placed:
        num_map[(wp['x'], wp['y'] - start_y)] = wp['num']
        
    for (x, y), num in num_map.items():
        draw.text((x * cell_size + 4, y * cell_size + 3), str(num), font=num_font, fill=0)
        
    return img

@register_module(
    type_id="crossword",
    label="Crossword",
    description="Generates a crossword puzzle",
    icon="grid-nine",
    offline=True,
    category="puzzles",
    config_schema={
        "type": "object",
        "properties": {
            "num_words": {
                "type": "integer",
                "title": "Number of Words",
                "default": 10,
                "minimum": 3,
                "maximum": 25
            },
            "difficulty": {
                "type": "string",
                "title": "Difficulty",
                "enum": ["Easy", "Medium", "Hard"],
                "default": "Easy"
            }
        }
    }
)
def execute_crossword(printer, config: Dict[str, Any], module_name: str = None):
    """Module entry point."""
    num_words = config.get("num_words", 10)
    difficulty = config.get("difficulty", "Easy")
    
    # Calculate dynamic block size to fill the paper width (384 dots)
    printer_width = getattr(printer, "PRINTER_WIDTH_DOTS", 384)
    block_size = (printer_width - 2) // GRID_WIDTH
    
    # 1. Load word list
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(app_dir, "data", "crossword_words.csv")
    
    easy_pool = []
    hard_pool = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                w = row['word'].strip().upper()
                h = row['hint'].strip()
                if w and h and w.isalpha() and 2 <= len(w) <= (GRID_WIDTH * 3):
                    d = row.get('difficulty', 'easy').strip().lower()
                    if d == 'hard':
                        hard_pool.append((w, h))
                    else:
                        easy_pool.append((w, h))
    except Exception as e:
        logger.error(f"Failed to load crossword words: {e}")
        printer.print_header(module_name or "CROSSWORD", icon="grid-nine")
        printer.print_body("Error: Could not load word list.")
        return
    
    # 2. Select words based on difficulty
    word_pool = []
    if difficulty == "Easy":
        word_pool = easy_pool
    elif difficulty == "Hard":
        word_pool = hard_pool
    else:  # Medium: 50/50 mix
        # We balance the pools to ensure an even distribution when the generator picks
        sample_size = min(len(easy_pool), len(hard_pool))
        word_pool = random.sample(easy_pool, sample_size) + random.sample(hard_pool, sample_size)

    if not word_pool:
        printer.print_header(module_name or "CROSSWORD", icon="grid-nine")
        printer.print_body("Error: Word list is empty.")
        return

    # 3. Generate Puzzle
    # CrosswordGenerator.generate now handles internal attempts and height growth
    gen = CrosswordGenerator(GRID_WIDTH, GRID_WIDTH)
    gen.generate(list(word_pool), num_words)
    
    if not gen.words_placed:
        printer.print_header(module_name or "CROSSWORD", icon="grid-nine")
        printer.print_body("Could not generate a puzzle layout.")
        return

    # 4. Print Header
    printer.print_header(module_name or "CROSSWORD", icon="grid-nine")
    printer.print_caption(format_print_datetime())
    printer.print_subheader(f"Level: {difficulty}")
    printer.feed(1)

    # 5. Print Grid
    # Get font path from driver if possible to match styles
    font_path = None
    if hasattr(printer, "_get_font"):
        # Attempt to find the path of a loaded font
        f = printer._get_font("regular")
        if hasattr(f, "path"):
            font_path = f.path
            
    grid_img = render_crossword_grid(gen, block_size, font_path)
    printer.print_image(grid_img)
    printer.feed(1)

    # 6. Print Clues
    across = [w for w in gen.words_placed if w['dir'] == "across"]
    down = [w for w in gen.words_placed if w['dir'] == "down"]

    if across:
        printer.print_bold("ACROSS")
        for clue in sorted(across, key=lambda x: x['num']):
            printer.print_body(f"{clue['num']}. {clue['hint']}")
        printer.feed(1)

    if down:
        printer.print_bold("DOWN")
        for clue in sorted(down, key=lambda x: x['num']):
            printer.print_body(f"{clue['num']}. {clue['hint']}")
        printer.feed(1)

    # 7. Print Answer Key
    printer.print_line()
    printer.print_caption("Solution hidden below...")
    printer.feed(10)
    
    # Compact answer string
    answers = []
    for clue in sorted(gen.words_placed, key=lambda x: x['num']):
        answers.append(f"{clue['num']}{clue['dir'][0].upper()}:{clue['word']}")
    
    printer.print_caption("ANSWERS: " + ", ".join(answers))
    printer.feed(1)