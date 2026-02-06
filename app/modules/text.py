import re
from datetime import datetime
from html.parser import HTMLParser
from typing import List, Tuple

from app.config import TextConfig
from app.drivers.printer_mock import PrinterDriver
from app.module_registry import register_module


_HTML_TAG_PATTERN = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
_CHECKBOX_PATTERN = re.compile(r"^\[( |x|X)\]\s*(.*)$")


def _looks_like_html(content: str) -> bool:
    return bool(_HTML_TAG_PATTERN.search(content or ""))


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class _NoteHtmlParser(HTMLParser):
    """Parse a limited subset of rich note HTML into print-friendly blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: List[Tuple[str, str]] = []
        self._current_tag = None
        self._current_text: List[str] = []
        self._list_stack = []
        self._ignore_depth = 0

    def _start_block(self, tag: str):
        self._close_block()
        self._current_tag = tag
        self._current_text = []

    def _close_block(self):
        if not self._current_tag:
            return

        raw_text = "".join(self._current_text).replace("\r\n", "\n").replace("\r", "\n")
        lines = [_normalize_whitespace(line) for line in raw_text.split("\n")]
        lines = [line for line in lines if line]
        text = "\n".join(lines).strip()

        if text:
            tag = self._current_tag
            if tag == "li":
                depth = max(0, len(self._list_stack) - 1)
                indent = "  " * depth

                if self._list_stack and self._list_stack[-1]["type"] == "ol":
                    marker = f"{self._list_stack[-1]['index']}."
                    self._list_stack[-1]["index"] += 1
                else:
                    marker = "-"

                text = f"{indent}{marker} {text}"
                tag = "p"

            self.blocks.append((tag, text))

        self._current_tag = None
        self._current_text = []

    def handle_starttag(self, tag: str, attrs):
        tag = tag.lower()

        if tag in {"script", "style"}:
            self._ignore_depth += 1
            return

        if self._ignore_depth:
            return

        if tag in {"ul", "ol"}:
            self._close_block()
            self._list_stack.append({"type": tag, "index": 1})
            return

        if tag == "li":
            self._start_block("li")
            return

        if tag in {"p", "div", "h1", "h2"}:
            self._start_block(tag)
            return

        if tag == "br" and self._current_tag:
            self._current_text.append("\n")

    def handle_endtag(self, tag: str):
        tag = tag.lower()

        if tag in {"script", "style"}:
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return

        if self._ignore_depth:
            return

        if tag in {"li", "p", "div", "h1", "h2"}:
            self._close_block()
            return

        if tag in {"ul", "ol"}:
            self._close_block()
            for index in range(len(self._list_stack) - 1, -1, -1):
                if self._list_stack[index]["type"] == tag:
                    self._list_stack = self._list_stack[:index]
                    break

    def handle_data(self, data: str):
        if self._ignore_depth:
            return

        if self._current_tag is None:
            if not data.strip():
                return
            self._start_block("p")

        self._current_text.append(data)

    def get_blocks(self) -> List[Tuple[str, str]]:
        self._close_block()
        return self.blocks


def _print_line(printer: PrinterDriver, line: str):
    line = line.strip()
    if not line:
        return

    checkbox_match = _CHECKBOX_PATTERN.match(line)
    if checkbox_match:
        marker_state = checkbox_match.group(1).lower()
        marker = "[x]" if marker_state == "x" else "[ ]"
        text = checkbox_match.group(2).strip()
        printer.print_body(f"{marker} {text}".rstrip())
        return

    printer.print_body(line)


def _print_rich_content(printer: PrinterDriver, content: str):
    parser = _NoteHtmlParser()
    parser.feed(content)
    blocks = parser.get_blocks()

    for tag, text in blocks:
        if tag == "h1":
            printer.print_text(text.upper(), "bold_lg")
        elif tag == "h2":
            printer.print_text(text, "semibold")
        else:
            for line in text.split("\n"):
                _print_line(printer, line)


@register_module(
    type_id="text",
    label="Text / Note",
    description="Print custom text or notes",
    icon="note",
    offline=True,
    category="utilities",
    config_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "title": "Content",
                "default": "",
            }
        },
    },
    ui_schema={
        "content": {
            "ui:widget": "note-editor",
            "ui:placeholder": "Write your note...",
        }
    },
)
def format_text_receipt(printer: PrinterDriver, config: TextConfig, module_name: str = None):
    """Prints a static text note."""

    header_label = module_name or "NOTE"
    printer.print_header(header_label, icon="note")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()

    content = (config.content or "").strip()
    if not content:
        printer.print_body("No content.")
    elif _looks_like_html(content):
        _print_rich_content(printer, content)
    else:
        printer.print_body(content)

    printer.print_line()
