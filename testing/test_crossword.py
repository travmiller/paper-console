from collections import defaultdict
import csv
import os

import pytest
from unittest.mock import MagicMock
from app.modules.crossword import CrosswordGenerator, execute_crossword

def test_crossword_generator_initialization():
    """Verify the generator initializes with correct dimensions."""
    gen = CrosswordGenerator(8, 60)
    assert gen.width == 8
    assert gen.height == 60
    assert len(gen.grid) == 60
    assert len(gen.grid[0]) == 8

def test_crossword_can_place_logic():
    """Test the overlap and adjacency logic for word placement."""
    gen = CrosswordGenerator(10, 10)
    
    # Place initial word
    gen.place("CAT", "Feline", 0, 0, "across", 1)
    
    # Valid intersection (shares 'A' at grid[0][1], which is x=1, y=0)
    assert gen.can_place("ACT", 1, 0, "down") is True
    
    # Edge Case: Invalid overlap (conflicting letter)
    assert gen.can_place("DOG", 0, 0, "down") is False
    
    # Edge Case: Invalid adjacency (too close to existing word)
    assert gen.can_place("DOG", 0, 1, "across") is False

def test_crossword_bounds_checks():
    """Verify words cannot be placed outside grid dimensions or at negative coordinates."""
    gen = CrosswordGenerator(8, 8)
    # Fits exactly across
    assert gen.can_place("ABCDEFGH", 0, 0, "across") is True
    # Too long across
    assert gen.can_place("ABCDEFGHI", 0, 0, "across") is False
    # Negative start
    assert gen.can_place("CAT", -1, 0, "across") is False
    assert gen.can_place("CAT", 0, -1, "across") is False
    # Fits exactly down
    assert gen.can_place("ABCDEFGH", 0, 0, "down") is True
    # Too long down
    assert gen.can_place("ABCDEFGHI", 0, 0, "down") is False

def test_crossword_adjacency_blocking():
    """Ensure words aren't placed immediately adjacent to others if it would create invalid letter clusters."""
    gen = CrosswordGenerator(10, 10)
    # Place a word in the middle
    gen.place("CAT", "Feline", 2, 2, "across", 1)
    
    # Parallel word directly above should fail
    assert gen.can_place("DOG", 2, 1, "across") is False
    # Parallel word directly below should fail
    assert gen.can_place("DOG", 2, 3, "across") is False
    # Word starting exactly where another ends should fail
    assert gen.can_place("BAT", 5, 2, "across") is False
    # Word ending exactly where another starts should fail
    assert gen.can_place("BAT", 0, 2, "across") is False

def test_crossword_overlap_calculation():
    """Verify the overlap percentage math: (sum of lengths - unique cells) / sum of lengths."""
    gen = CrosswordGenerator(8, 8)
    # Two words, 0 overlap
    gen.place("CAT", "Hint", 0, 0, "across", 1)
    gen.place("DOG", "Hint", 0, 2, "across", 2)
    assert gen._calculate_overlap() == 0.0

    # Clear and try an actual intersection
    gen = CrosswordGenerator(8, 8)
    gen.place("CAT", "Hint", 0, 0, "across", 1)
    gen.place("ACT", "Hint", 1, 0, "down", 2)
    # C A T (3 cells)
    #   C
    #   T   (A is shared, so total unique cells = 5. Total word length = 6)
    # (6 - 5) / 6 = 1/6
    assert gen._calculate_overlap() == pytest.approx(1/6)

def test_crossword_scoring_logic():
    """Test the puzzle scoring algorithm components."""
    gen = CrosswordGenerator(8, 8)
    # score = (num_words * 1000) + (overlap * 500) - (height * 10)
    
    # 5 words, 20% overlap, 10 height
    # 5000 + 100 - 100 = 5000
    score1 = gen._calculate_puzzle_score(5, 0.2, 10)
    assert score1 == 5000

    # 5 words, 50% overlap, 15 height
    # 5000 + 250 - 150 = 5100 (Higher overlap beats lower height penalty)
    score2 = gen._calculate_puzzle_score(5, 0.5, 15)
    assert score2 > score1
    assert score2 == 5100

def test_no_duplicate_words():
    file_path = "../app/data/crossword_words.csv"
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    # Dictionary to store word occurrences: { WORD: [row_data, ...] }
    word_map = defaultdict(list)
    
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Clean and normalize the word
            word = row['word'].strip().upper()
            word_map[word].append(row)
            
    # Filter for words that appear more than once
    duplicates = {word: rows for word, rows in word_map.items() if len(rows) > 1}
    
    if duplicates:
        print(f"Found {len(duplicates)} duplicate words:\n")
        
        for word, occurrences in duplicates.items():
            print(f"Word: {word}")
            print(f"Count: {len(occurrences)}")
            for i, row in enumerate(occurrences, 1):
                hint = row.get('hint', 'No hint provided')
                diff = row.get('difficulty', 'unknown')
                print(f"  {i}. [{diff}] {hint}")
            print("-" * 30)
    
    assert not duplicates, "Duplicate words found in the crossword word list"