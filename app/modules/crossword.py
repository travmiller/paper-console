import random
from typing import Dict, Any, List, Tuple, Optional


class CrosswordGenerator:
    def __init__(self, size: int = 12):
        self.size = size
        self.grid = [[' ' for _ in range(size)] for _ in range(size)]
        self.clues = []
        self.word_list = [
            'HELLO', 'WORLD', 'PUZZLE', 'SOLVE', 'CLUE',
            'ACROSS', 'DOWN', 'WORD', 'GRID', 'FILL',
            'LETTER', 'SPACE', 'BLANK', 'ANSWER', 'GAME',
            'FUN', 'BRAIN', 'THINK', 'LOGIC', 'SMART'
        ]
        
    def can_place_word(self, word: str, row: int, col: int, direction: str) -> bool:
        """Check if a word can be placed at the given position."""
        if direction == 'across':
            if col + len(word) > self.size:
                return False
            for i, char in enumerate(word):
                if self.grid[row][col + i] != ' ' and self.grid[row][col + i] != char:
                    return False
        else:  # down
            if row + len(word) > self.size:
                return False
            for i, char in enumerate(word):
                if self.grid[row + i][col] != ' ' and self.grid[row + i][col] != char:
                    return False
        return True
    
    def place_word(self, word: str, row: int, col: int, direction: str, clue_num: int):
        """Place a word on the grid."""
        if direction == 'across':
            for i, char in enumerate(word):
                self.grid[row][col + i] = char
        else:  # down
            for i, char in enumerate(word):
                self.grid[row + i][col] = char
        
        self.clues.append({
            'number': clue_num,
            'word': word,
            'row': row,
            'col': col,
            'direction': direction
        })
    
    def generate(self, num_words: int = 8):
        """Generate a crossword puzzle."""
        # Shuffle word list
        available_words = self.word_list.copy()
        random.shuffle(available_words)
        
        # Try to place words
        placed_words = []
        clue_num = 1
        
        # Place first word horizontally in the middle
        if available_words:
            first_word = available_words.pop(0)
            start_row = self.size // 2
            start_col = (self.size - len(first_word)) // 2
            self.place_word(first_word, start_row, start_col, 'across', clue_num)
            placed_words.append((first_word, start_row, start_col, 'across'))
            clue_num += 1
        
        # Try to place more words intersecting with existing ones
        attempts = 0
        max_attempts = num_words * 20
        
        while len(placed_words) < num_words and available_words and attempts < max_attempts:
            attempts += 1
            word = random.choice(available_words)
            
            # Try to find an intersection with an existing word
            best_placement = None
            best_score = 0
            
            for placed_word, p_row, p_col, p_dir in placed_words:
                # Try to find a common letter
                for i, char in enumerate(word):
                    for j, p_char in enumerate(placed_word):
                        if char == p_char:
                            if p_dir == 'across':
                                # Try placing word down
                                new_row = p_row - i
                                new_col = p_col + j
                                if self.can_place_word(word, new_row, new_col, 'down'):
                                    score = len(placed_word) + len(word)
                                    if score > best_score:
                                        best_score = score
                                        best_placement = (word, new_row, new_col, 'down', clue_num)
                            else:  # p_dir == 'down'
                                # Try placing word across
                                new_row = p_row + j
                                new_col = p_col - i
                                if self.can_place_word(word, new_row, new_col, 'across'):
                                    score = len(placed_word) + len(word)
                                    if score > best_score:
                                        best_score = score
                                        best_placement = (word, new_row, new_col, 'across', clue_num)
            
            if best_placement:
                word, row, col, direction, num = best_placement
                self.place_word(word, row, col, direction, num)
                placed_words.append((word, row, col, direction))
                available_words.remove(word)
                clue_num += 1
        
        # Sort clues by number
        self.clues.sort(key=lambda x: x['number'])


def format_crossword_receipt(printer, config: Dict[str, Any] = None, module_name: str = None):
    """Prints a crossword puzzle."""
    from datetime import datetime
    
    size = config.get('size', 12) if config else 12
    num_words = config.get('num_words', 8) if config else 8
    
    # Generate crossword
    generator = CrosswordGenerator(size)
    generator.generate(num_words)
    
    # Header
    printer.print_header((module_name or "CROSSWORD").upper())
    printer.print_text(datetime.now().strftime("%A, %b %d"))
    printer.print_line()
    
    # Print grid
    # Create a grid with numbers for clue starts
    clue_positions = {}
    for clue in generator.clues:
        key = (clue['row'], clue['col'])
        if key not in clue_positions:
            clue_positions[key] = []
        clue_positions[key].append(clue['number'])
    
    # Print grid with |_| for empty cells and |A| for filled cells
    # Format: |1||H||E||L||L||O| for cells with content
    #         |_||_||_||_||_||_| for empty cells
    max_width = getattr(printer, 'width', 32)
    
    # Calculate how many cells fit (each cell is 2 chars: |X| or |_|)
    # With 32 chars, we can fit 12 cells: |X||X||X|... = 24 chars
    cells_per_row = min(size, max_width // 2)
    
    for i, row in enumerate(generator.grid):
        # Build content line
        content_line = ""
        
        for j in range(cells_per_row):
            cell = row[j] if j < len(row) else ' '
            
            if (i, j) in clue_positions:
                # Show clue number (single digit) in format |N|
                nums = clue_positions[(i, j)]
                content_line += f"|{nums[0]}|"
            elif cell == ' ':
                # Empty cell: |_|
                content_line += "|_|"
            else:
                # Show the letter in format |L|
                content_line += f"|{cell}|"
        
        # Print content line
        printer.print_text(content_line[:max_width])
    
    printer.print_line()
    
    # Print clues
    printer.print_text("CLUES:")
    printer.print_line()
    
    across_clues = [c for c in generator.clues if c['direction'] == 'across']
    down_clues = [c for c in generator.clues if c['direction'] == 'down']
    
    if across_clues:
        printer.print_text("ACROSS:")
        for clue in across_clues:
            # Simple clue: just show length
            printer.print_text(f"{clue['number']}. ({len(clue['word'])} letters)")
    
    printer.feed(1)
    
    if down_clues:
        printer.print_text("DOWN:")
        for clue in down_clues:
            printer.print_text(f"{clue['number']}. ({len(clue['word'])} letters)")
    
    printer.print_line()
    printer.print_text("Fill in the words!")
    printer.feed(1)

