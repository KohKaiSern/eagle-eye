"""Text reader for DOCX contracts."""

from typing import TypedDict

from docx import Document
from docx.text.paragraph import Paragraph


class DOCXResult(TypedDict):
    """The text and confidence returned by the DOCX reader."""

    text: str
    confidence: float


def read_docx(filepath: str) -> DOCXResult:
    """Extract text from a DOCX contract while ignoring embedded images.

    Paragraphs and tables are emitted in document order. Text read directly
    from the DOCX structure has confidence 1.0; a document with no text has
    confidence 0.0.
    """

    document = Document(filepath)
    blocks: list[str] = []

    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            if text := block.text.strip():
                blocks.append(text)
            continue

        for row in block.rows:
            cells: list[str] = []
            seen_cells: set[int] = set()

            for cell in row.cells:
                cell_id = id(cell._tc)
                if cell_id in seen_cells:
                    continue

                seen_cells.add(cell_id)
                cells.append(cell.text.strip())

            if row_text := "\t".join(cells).strip():
                blocks.append(row_text)

    text = "\n".join(blocks)
    return {"text": text, "confidence": 1.0 if text else 0.0}
