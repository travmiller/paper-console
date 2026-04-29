import csv
import random
import os
import logging
import string
from typing import List, Dict, Tuple, Optional, Any
from PIL import Image, ImageDraw, ImageFont
from app.module_registry import register_module
from app.config import format_print_datetime

logger = logging.getLogger(__name__)

# Direction Constants (dx, dy)
DIR_RIGHT = (1, 0)
DIR_DOWN = (0, 1)
DIR_DOWN_RIGHT = (1, 1)
DIR_UP_RIGHT = (1, -1)
DIR_LEFT = (-1, 0)
DIR_UP = (0, -1)
DIR_UP_LEFT = (-1, -1)
DIR_DOWN_LEFT = (-1, 1)

DIRECTIONS_EASY = [DIR_RIGHT, DIR_DOWN, DIR_DOWN_RIGHT, DIR_UP_RIGHT]
DIRECTIONS_HARD = [DIR_RIGHT, DIR_DOWN, DIR_DOWN_RIGHT, DIR_UP_RIGHT, DIR_LEFT, DIR_UP, DIR_UP_LEFT, DIR_DOWN_LEFT]

class WordSearchGenerator:
    """
    Generator for word search puzzles.
    """
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid = [['' for _ in range(width)] for _ in range(height)]
        self.words_placed = []

    def can_place(self, word: str, x: int, y: int, dx: int, dy: int) -> bool:
        """Check if a word can be placed at (x, y) in direction (dx, dy)."""
        if not (0 <= x + dx * (len(word) - 1) < self.width): return False
        if not (0 <= y + dy * (len(word) - 1) < self.height): return False
        
        for i, char in enumerate(word):
            curr_x, curr_y = x + dx * i, y + dy * i
            if self.grid[curr_y][curr_x] != "" and self.grid[curr_y][curr_x] != char:
                return False
        return True

    def place(self, word: str, x: int, y: int, dx: int, dy: int):
        """Place a word on the grid."""
        for i, char in enumerate(word):
            self.grid[y + dy * i][x + dx * i] = char
        self.words_placed.append({'word': word, 'start_x': x, 'start_y': y, 'dx': dx, 'dy': dy})

    def _calculate_overlap(self) -> float:
        """Calculates the percentage of placed words that overlap with at least one other word."""
        if len(self.words_placed) < 2: return 0.0
        
        total_cells = set()
        for placement in self.words_placed:
            for k in range(len(placement['word'])):
                total_cells.add((placement['start_x'] + placement['dx'] * k,
                                  placement['start_y'] + placement['dy'] * k))

        # Count unique cells occupied by words
        unique_word_cells = len(total_cells)

        # Calculate total cells if words were placed without any overlap
        sum_of_word_lengths = sum(len(p['word']) for p in self.words_placed)

        if sum_of_word_lengths == 0: return 0.0

        # Overlap is (sum of lengths - unique cells) / sum of lengths
        return (sum_of_word_lengths - unique_word_cells) / sum_of_word_lengths

    def _calculate_puzzle_score(self, num_words_placed: int, overlap_percentage: float) -> float:
        """
        Calculates a score for the puzzle based on words placed and overlap.
        Prioritizes more words and higher overlap.
        """
        # Scale factors to give more weight to words placed and then overlap
        score = (num_words_placed * 1000) + (overlap_percentage * 100)
        return score

    def generate(self, word_pool: List[str], num_words: int, directions: List[Tuple[int, int]]):
        """Fill the grid with words from the pool and fill remaining with random letters."""
        # Sort word_pool by length descending to prioritize placing longer words first
        word_pool.sort(key=len, reverse=True)
        
        max_height = 40  # Maximum height to prevent infinite growth
        best_grid = None
        best_words_placed = []
        best_score = -1.0

        # Growth loop: increase height if words don't fit
        while self.height <= max_height:
            placed_all_at_this_height = False
            
            # Multiple attempts per height to maximize overlap
            for attempt in range(40):
                current_attempt_grid = [['' for _ in range(self.width)] for _ in range(self.height)]
                current_attempt_words_placed = []

                # Context swap for internal class logic
                original_grid = self.grid
                original_words_placed = self.words_placed
                self.grid = current_attempt_grid
                self.words_placed = current_attempt_words_placed
                
                current_word_pool = list(set(word_pool))
                random.shuffle(current_word_pool)
                
                count = 0
                for word in current_word_pool:
                    if count >= num_words: break
                    
                    placed = False
                    max_placement_attempts = self.width * self.height * 2
                    placement_attempts = 0 
                    while not placed and placement_attempts < max_placement_attempts:
                        dx, dy = random.choice(directions)
                        
                        # Basic fit check before calculating precise bounds
                        if (dx != 0 and len(word) > self.width) or (dy != 0 and len(word) > self.height):
                            placement_attempts += 1
                            continue

                        min_x = 0 if dx >= 0 else len(word) - 1
                        max_x = self.width - 1 if dx <= 0 else self.width - len(word)
                        min_y = 0 if dy >= 0 else len(word) - 1
                        max_y = self.height - 1 if dy <= 0 else self.height - len(word)

                        if min_x > max_x or min_y > max_y:
                            placement_attempts += 1
                            continue
                            
                        x = random.randint(min_x, max_x)
                        y = random.randint(min_y, max_y)
                        
                        if self.can_place(word, x, y, dx, dy):
                            self.place(word, x, y, dx, dy)
                            placed = True
                            count += 1
                        placement_attempts += 1
                
                current_overlap = self._calculate_overlap()
                current_score = self._calculate_puzzle_score(len(self.words_placed), current_overlap)

                if len(self.words_placed) == num_words:
                    placed_all_at_this_height = True

                if current_score > best_score:
                    best_score = current_score
                    best_grid = [row[:] for row in self.grid]
                    best_words_placed = list(self.words_placed)
                    logger.debug(f"H={self.height}: New best score {best_score:.2f} with {len(best_words_placed)} words.")

                self.grid = original_grid
                self.words_placed = original_words_placed
            
            if placed_all_at_this_height:
                break
            
            self.height += 1
            logger.debug(f"Growing wordsearch grid to height {self.height}")

        # After all attempts, apply the best found puzzle
        if best_grid is not None:
            self.grid = best_grid
            self.words_placed = best_words_placed
            self.height = len(self.grid)

            # Place distractor words (words from pool not in the target find list)
            target_words_set = {p['word'] for p in self.words_placed}
            distractor_pool = [w for w in word_pool if w not in target_words_set]
            random.shuffle(distractor_pool)
            
            # Try to add some distractors - up to half of the find list or max 8
            num_distractors = min(len(distractor_pool), num_words // 2, 8)
            distractors_added = 0
            
            for distractor in distractor_pool:
                if distractors_added >= num_distractors:
                    break
                
                # Limited attempts per distractor to keep generation fast
                for _ in range(15):
                    dx, dy = random.choice(directions)
                    
                    if (dx != 0 and len(distractor) > self.width) or (dy != 0 and len(distractor) > self.height):
                        continue

                    min_x = 0 if dx >= 0 else len(distractor) - 1
                    max_x = self.width - 1 if dx <= 0 else self.width - len(distractor)
                    min_y = 0 if dy >= 0 else len(distractor) - 1
                    max_y = self.height - 1 if dy <= 0 else self.height - len(distractor)

                    if min_x > max_x or min_y > max_y:
                        continue
                        
                    x = random.randint(min_x, max_x)
                    y = random.randint(min_y, max_y)
                    
                    if self.can_place(distractor, x, y, dx, dy):
                        # Manual placement (bypassing self.place so they aren't added to target list)
                        for i, char in enumerate(distractor):
                            self.grid[y + dy * i][x + dx * i] = char
                        distractors_added += 1
                        break

        else:
            logger.warning(f"Could not generate a full word search after growing to height {self.height}.")
        
        # Fill remaining empty cells with random letters
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y][x] == "":
                    self.grid[y][x] = random.choice(string.ascii_uppercase)

def render_wordsearch_grid(grid: List[List[str]], cell_size: int, font_path: str = None) -> Image.Image:
    """Renders the word search grid as a 1-bit bitmap."""
    height = len(grid)
    width = len(grid[0]) if height > 0 else 0
    img_w = width * cell_size + 2
    img_h = height * cell_size + 2
    img = Image.new("1", (img_w, img_h), 1) # White background
    draw = ImageDraw.Draw(img)
    
    try:
        # Use a bold/thick font for readability
        font_size = int(cell_size * 0.7)
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    # Draw grid lines for clarity
    for i in range(width + 1):
        pos = i * cell_size + 1
        draw.line([(pos, 0), (pos, img_h)], fill=0)
    for i in range(height + 1):
        pos = i * cell_size + 1
        draw.line([(0, pos), (img_w, pos)], fill=0)

    # Draw letters
    for y, row in enumerate(grid):
        for x, char in enumerate(row):
            if font:
                bbox = draw.textbbox((0, 0), char, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                
                # Center text in cell
                text_x = x * cell_size + (cell_size - w) // 2 + 1 - bbox[0]
                text_y = y * cell_size + (cell_size - h) // 2 + 1 - bbox[1]
                draw.text((text_x, text_y), char, font=font, fill=0)
            else:
                draw.text((x * cell_size + cell_size // 4, y * cell_size + cell_size // 4), char, fill=0)
                
    return img

@register_module(
    type_id="wordsearch",
    label="Word Search",
    description="Generates a word search puzzle",
    icon="magnifying-glass",
    offline=True,
    category="games",
    config_schema={
        "type": "object",
        "properties": {
            "num_words": {
                "type": "integer",
                "title": "Number of Words",
                "default": 15,
                "minimum": 5,
                "maximum": 30
            },
            "difficulty": {
                "type": "string",
                "title": "Difficulty",
                "enum": ["Easy", "Hard"],
                "default": "Easy"
            }
        }
    }
)
def execute_wordsearch(printer, config: Dict[str, Any], module_name: str = None):
    """Word search module implementation."""
    num_words = config.get("num_words", 15)
    difficulty = config.get("difficulty", "Hard")
    
    # 1. Load word list from the shared crossword source
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(app_dir, "data", "crossword_words.csv")
    
    word_pool = []
    try:
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    w = row['word'].strip().upper()
                    # Include words that fit within the maximum possible grid dimension (20)
                    if w and 3 <= len(w) <= 20 and w.isalpha():
                        word_pool.append(w)

    except Exception as e:
        logger.error(f"Failed to load word search words: {e}")
        printer.print_header(module_name or "WORD SEARCH", icon="magnifying-glass")
        printer.print_body("Error: Could not load word list.")
        return

    if not word_pool:
        printer.print_header(module_name or "WORD SEARCH", icon="magnifying-glass")
        printer.print_body("Error: Word list is empty.")
        return

    # 2. Determine settings based on difficulty (constant width 12, varying height)
    grid_width = 12
    grid_height = 12 # Fixed initial height for all difficulties
    
    if difficulty == "Easy":
        directions = DIRECTIONS_EASY
    else: # Hard
        directions = DIRECTIONS_HARD

    # 3. Generate Puzzle
    gen = WordSearchGenerator(grid_width, grid_height)
    # Words must fit within width (12) or the maximum possible growth height (approx 20)
    valid_pool = [w for w in word_pool if len(w) <= 20]
    gen.generate(valid_pool, num_words, directions)
    
    # 4. Print Layout
    printer.print_header(module_name or "WORD SEARCH", icon="magnifying-glass")
    printer.print_caption(format_print_datetime())
    printer.print_subheader(f"Level: {difficulty}")
    printer.feed(1)

    # Calculate cell size to fill width (384 dots)
    printer_width = getattr(printer, "PRINTER_WIDTH_DOTS", 384)
    cell_size = (printer_width - 4) // grid_width
    
    font_path = None
    if hasattr(printer, "_get_font"):
        f = printer._get_font("bold")
        if hasattr(f, "path"):
            font_path = f.path
            
    grid_img = render_wordsearch_grid(gen.grid, cell_size, font_path)
    printer.print_image(grid_img)
    printer.feed(1)

    # 5. Word List
    printer.print_bold("FIND THESE WORDS:")
    # Sort for easier reading
    placed_words = sorted([p['word'] for p in gen.words_placed])
    printer.print_body(", ".join(placed_words))
    
    printer.feed(1)