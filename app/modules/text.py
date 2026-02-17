from typing import Any, Dict, List
from app.config import TextConfig
from app.drivers.printer_mock import PrinterDriver
from app.module_registry import register_module

DEFAULT_CONTENT_DOC = {"type": "doc", "content": [{"type": "paragraph"}]}


@register_module(
    type_id="text",
    label="Text / Note",
    description="Print custom rich text notes",
    icon="note",
    offline=True,
    category="utilities",
    config_schema={
        "type": "object",
        "properties": {
            "content_doc": {
                "type": "object",
                "title": "Content",
                "default": DEFAULT_CONTENT_DOC,
            }
        },
    },
    ui_schema={
        "content_doc": {
            "ui:widget": "richtext",
            "ui:placeholder": "Enter text to print...",
        }
    },
)
def format_text_receipt(printer: PrinterDriver, config: TextConfig, module_name: str = None):
    """Prints a static text note from a TipTap JSON document."""
    from datetime import datetime
    
    header_label = module_name or "NOTE"
    printer.print_header(header_label, icon="note")
    printer.print_caption(datetime.now().strftime("%A, %B %d, %Y"))
    printer.print_line()
    
    content_doc = _normalize_content_doc(config.content_doc)

    if _doc_has_visible_content(content_doc):
        _print_rich_doc(printer, content_doc)
    else:
        printer.print_body("No content.")
    
    printer.print_line()


def _normalize_content_doc(content_doc: Any) -> Dict[str, Any]:
    if not isinstance(content_doc, dict):
        return {"type": "doc", "content": [{"type": "paragraph"}]}

    if content_doc.get("type") != "doc":
        return {"type": "doc", "content": [{"type": "paragraph"}]}

    content = content_doc.get("content")
    if not isinstance(content, list):
        return {"type": "doc", "content": []}

    return content_doc


def _doc_has_visible_content(node: Any) -> bool:
    if not isinstance(node, dict):
        return False

    node_type = node.get("type")
    if node_type == "horizontalRule":
        return True
    if node_type == "text":
        return bool((node.get("text") or "").strip())

    children = node.get("content") or []
    if not isinstance(children, list):
        return False
    return any(_doc_has_visible_content(child) for child in children)


def _print_rich_doc(printer: PrinterDriver, doc: Dict[str, Any]):
    for node in doc.get("content", []):
        _print_block_node(printer, node, indent="")


def _print_block_node(printer: PrinterDriver, node: Dict[str, Any], indent: str = ""):
    if not isinstance(node, dict):
        return

    node_type = node.get("type")

    if node_type == "heading":
        heading_text = _extract_plain_text(node).strip()
        if heading_text:
            _print_multiline(printer, f"{indent}{heading_text}", style="bold_lg")
        return

    if node_type == "paragraph":
        paragraph_text = _extract_plain_text(node)
        style = _infer_paragraph_style(node)
        _print_multiline(printer, f"{indent}{paragraph_text}", style=style, allow_blank=True)
        return

    if node_type == "horizontalRule":
        printer.print_line()
        return

    if node_type == "bulletList":
        _print_unordered_list(printer, node, indent)
        return

    if node_type == "orderedList":
        _print_ordered_list(printer, node, indent)
        return

    if node_type == "taskList":
        _print_task_list(printer, node, indent)
        return

    # Unknown block fallback: print extracted text if present.
    fallback_text = _extract_plain_text(node).strip()
    if fallback_text:
        _print_multiline(printer, f"{indent}{fallback_text}", style="regular")


def _print_unordered_list(printer: PrinterDriver, node: Dict[str, Any], indent: str):
    for item in node.get("content", []):
        _print_list_item(printer, item, prefix=f"{indent}• ", child_indent=f"{indent}  ")


def _print_ordered_list(printer: PrinterDriver, node: Dict[str, Any], indent: str):
    attrs = node.get("attrs") or {}
    start = attrs.get("start", 1)
    try:
        index = int(start)
    except Exception:
        index = 1

    for item in node.get("content", []):
        _print_list_item(printer, item, prefix=f"{indent}{index}. ", child_indent=f"{indent}   ")
        index += 1


def _print_task_list(printer: PrinterDriver, node: Dict[str, Any], indent: str):
    for item in node.get("content", []):
        if not isinstance(item, dict):
            continue
        attrs = item.get("attrs") or {}
        checked = bool(attrs.get("checked"))
        checkbox = "[x]" if checked else "[ ]"
        _print_list_item(printer, item, prefix=f"{indent}{checkbox} ", child_indent=f"{indent}    ")


def _print_list_item(
    printer: PrinterDriver,
    item: Dict[str, Any],
    prefix: str,
    child_indent: str,
):
    if not isinstance(item, dict):
        return

    children = item.get("content") or []
    if not isinstance(children, list):
        children = []

    printed_primary = False
    deferred_nodes: List[Dict[str, Any]] = []

    for child in children:
        if not isinstance(child, dict):
            continue

        child_type = child.get("type")
        if child_type in {"bulletList", "orderedList", "taskList"}:
            deferred_nodes.append(child)
            continue

        if not printed_primary and child_type in {"paragraph", "heading"}:
            text = _extract_plain_text(child).strip()
            style = "bold" if child_type == "heading" else _infer_paragraph_style(child)
            if text:
                _print_multiline(printer, f"{prefix}{text}", style=style)
            else:
                _print_multiline(printer, prefix.rstrip(), style="regular")
            printed_primary = True
            continue

        deferred_nodes.append(child)

    if not printed_primary:
        _print_multiline(printer, prefix.rstrip(), style="regular")

    for node in deferred_nodes:
        _print_block_node(printer, node, indent=child_indent)


def _print_multiline(
    printer: PrinterDriver,
    text: str,
    style: str = "regular",
    allow_blank: bool = False,
):
    if text == "":
        if allow_blank:
            _print_blank_line(printer)
        return

    for line in text.split("\n"):
        if line == "":
            if allow_blank:
                _print_blank_line(printer)
            continue
        printer.print_text(line, style)


def _print_blank_line(printer: PrinterDriver):
    if hasattr(printer, "feed"):
        printer.feed(1)
    else:
        printer.print_text(" ", "regular")


def _extract_plain_text(node: Any) -> str:
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type")
    if node_type == "text":
        return node.get("text") or ""
    if node_type == "hardBreak":
        return "\n"

    children = node.get("content") or []
    if not isinstance(children, list):
        return ""
    return "".join(_extract_plain_text(child) for child in children)


def _infer_paragraph_style(node: Dict[str, Any]) -> str:
    """Infer a single style for a paragraph when all marked text agrees."""
    children = node.get("content") or []
    if not isinstance(children, list):
        return "regular"

    mark_sets = []
    for child in children:
        if not isinstance(child, dict) or child.get("type") != "text":
            continue
        text = child.get("text") or ""
        if not text.strip():
            continue

        marks = child.get("marks") or []
        if not isinstance(marks, list):
            marks = []
        mark_types = set()
        for mark in marks:
            if isinstance(mark, dict) and mark.get("type"):
                mark_types.add(mark["type"])
        mark_sets.append(mark_types)

    if not mark_sets:
        return "regular"
    if all(mark_set == {"bold"} for mark_set in mark_sets):
        return "bold"
    if all(mark_set == {"italic"} for mark_set in mark_sets):
        return "italic"
    if all("bold" in mark_set for mark_set in mark_sets):
        return "bold"
    if all("italic" in mark_set for mark_set in mark_sets):
        return "italic"
    return "regular"
