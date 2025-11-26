"""Shared utility functions for modules."""


def wrap_text(text: str, width: int = 32, indent: int = 0) -> list[str]:
    """Wraps text to fit the printer width with optional indentation."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        available_width = width - indent

        if len(current_line) + len(word) + 1 <= available_width:
            current_line += word + " "
        else:
            if current_line:
                lines.append(current_line.strip())
            current_line = word + " "

    if current_line:
        lines.append(current_line.strip())

    return lines

